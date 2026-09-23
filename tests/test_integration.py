"""Exercise the application in real, disposable tmux terminals."""

import shlex
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


class Terminal:
    """An isolated source server and terminal hosting just run."""

    def __init__(self, binary: str, source: str, terminal: str) -> None:
        self.binary = binary
        self.source = source
        self.terminal = terminal

    def command(self, socket: str, *arguments: str) -> str:
        """Run a checked command against the specified private server."""
        return subprocess.run([self.binary, "-S", socket, *arguments], check=True, text=True, capture_output=True).stdout

    def screen(self) -> str:
        """Read the visible application screen."""
        return self.command(self.terminal, "capture-pane", "-p", "-t", "driver")

    def wait_for(self, text: str) -> str:
        """Wait until a visible state is rendered, with a bounded deadline."""
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            output = self.screen()
            if text in output:
                return output
            time.sleep(0.05)
        raise AssertionError(f"Did not see {text!r}:\n{self.screen()}")

    def keys(self, *keys: str) -> None:
        """Send real terminal keys to the app."""
        self.command(self.terminal, "send-keys", "-t", "driver", *keys)


@pytest.fixture
def terminal() -> Iterator[Terminal]:
    binary = shutil.which("tmux")
    assert binary is not None, "Integration tests require tmux"
    with TemporaryDirectory(prefix="router-test-") as directory:
        source = str(Path(directory) / "source")
        driver = str(Path(directory) / "driver")
        terminal = Terminal(binary, source, driver)
        terminal.command(source, "-f", "/dev/null", "new-session", "-d", "-s", "zebra", "-c", "/tmp", "/bin/sh")
        try:
            terminal.command(source, "new-session", "-d", "-s", "alpha", "-c", "/tmp", "/bin/sh")
            launch = shlex.join(
                [
                    "env",
                    "-u",
                    "TMUX_PANE",
                    f"TMUX={source},0,0",
                    f"TMPDIR={directory}",
                    "UV_CACHE_DIR=/tmp/tmux-router-uv-cache",
                    "just",
                    "run",
                ]
            )
            terminal.command(driver, "-f", "/dev/null", "new-session", "-d", "-s", "driver", "-x", "120", "-y", "30")
            try:
                terminal.command(driver, "set-option", "-g", "status", "off")
                terminal.command(driver, "set-option", "-g", "remain-on-exit", "on")
                terminal.command(driver, "send-keys", "-t", "driver", launch, "Enter")
                terminal.wait_for("Enter the number")
                yield terminal
                terminal.keys("C-c")
            finally:
                terminal.command(driver, "kill-server")
        finally:
            terminal.command(source, "kill-server")


def test_native_proxy_and_return(terminal: Terminal) -> None:
    listing = terminal.screen()
    header = next(line for line in listing.splitlines() if "Working directory" in line)
    first_session = next(line for line in listing.splitlines() if "1. alpha" in line)
    assert header.index("Session") == first_session.index("alpha")
    assert header.index("Working directory") == first_session.index(str(Path("/tmp").resolve()))
    assert listing.index("1. alpha") < listing.index("2. zebra")
    terminal.keys("1", "Enter")
    terminal.wait_for("F1: return to sessions")
    terminal.keys("printf 'FORWARDED_OK\\n'", "Enter")
    terminal.wait_for("FORWARDED_OK")
    terminal.keys("cd /", "Enter")
    terminal.wait_for("You are currently in session alpha | /")
    terminal.keys("C-b", "c")
    deadline = time.monotonic() + 5
    windows = ""
    while time.monotonic() < deadline:
        windows = terminal.command(terminal.source, "list-windows", "-t", "alpha")
        if len(windows.splitlines()) == 2:
            break
        time.sleep(0.05)
    assert len(windows.splitlines()) == 2
    terminal.keys("F1")
    terminal.wait_for("Enter the number")
    clients = terminal.command(terminal.source, "list-clients")
    assert clients == ""
    assert "alpha" in terminal.command(terminal.source, "list-sessions")
    terminal.keys("Down", "9")
    assert "[B" not in terminal.wait_for("> 9")


def test_missing_session_waits_for_enter(terminal: Terminal) -> None:
    terminal.keys("1")
    terminal.command(terminal.source, "kill-session", "-t", "alpha")
    terminal.keys("Enter")
    terminal.wait_for("The selected session doesn't exist anymore.")
    terminal.keys("x")
    assert "Press Enter to continue." in terminal.screen()
    terminal.keys("Enter")
    terminal.wait_for("1. zebra")


def test_target_exit_returns_to_picker(terminal: Terminal) -> None:
    terminal.keys("1", "Enter")
    terminal.wait_for("F1: return to sessions")
    terminal.command(terminal.source, "kill-session", "-t", "alpha")
    terminal.wait_for("Enter the number")
    assert "1. zebra" in terminal.screen()


def test_status_follows_native_session_switch(terminal: Terminal) -> None:
    terminal.keys("1", "Enter")
    terminal.wait_for("You are currently in session alpha")
    client = terminal.command(terminal.source, "list-clients", "-F", "#{client_name}").strip()
    assert client
    terminal.command(terminal.source, "switch-client", "-c", client, "-t", "zebra")
    terminal.wait_for("You are currently in session zebra")
    terminal.keys("F1")
    terminal.wait_for("Enter the number")


def test_raw_keys_and_resize(terminal: Terminal, tmp_path: Path) -> None:
    captured = tmp_path / "keys"
    script = (
        "import os,sys,tty,termios; from pathlib import Path; "
        "fd=sys.stdin.fileno(); saved=termios.tcgetattr(fd); tty.setraw(fd); print('READY_FOR_KEYS',flush=True); "
        "data=b''\n"
        "try:\n"
        " while len(data)<10: data+=os.read(fd,10-len(data))\n"
        "finally: termios.tcsetattr(fd,termios.TCSANOW,saved)\n"
        f"Path({str(captured)!r}).write_bytes(data)"
    )
    uv = shutil.which("uv")
    assert uv is not None
    launch = shlex.join([uv, "run", "--project", str(Path.cwd()), "python", "-c", script])
    terminal.command(terminal.source, "send-keys", "-t", "alpha", "-l", launch)
    terminal.command(terminal.source, "send-keys", "-t", "alpha", "Enter")
    terminal.keys("1", "Enter")
    terminal.wait_for("READY_FOR_KEYS")
    terminal.wait_for("F1: return to sessions")
    terminal.keys("text", "Enter", "Up", "Escape", "C-c")
    deadline = time.monotonic() + 5
    while not captured.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert captured.read_bytes() == b"text\r\x1b[A\x1b\x03"
    terminal.command(terminal.terminal, "resize-window", "-t", "driver", "-x", "100", "-y", "25")
    size = ""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        size = terminal.command(terminal.source, "display-message", "-p", "-t", "alpha", "#{pane_width}x#{pane_height}").strip()
        if size == "100x23":
            break
        time.sleep(0.05)
    assert size == "100x23"
    terminal.keys("F1")
    terminal.wait_for("Enter the number")


def test_terminal_close_cleans_wrapper(terminal: Terminal) -> None:
    terminal.keys("1", "Enter")
    terminal.wait_for("F1: return to sessions")
    wrappers = list(Path(terminal.source).parent.glob("tmux-router-*"))
    assert len(wrappers) == 1
    terminal.command(terminal.terminal, "respawn-pane", "-k", "-t", "driver", "/bin/sh")
    deadline = time.monotonic() + 5
    while wrappers[0].exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not wrappers[0].exists()
    clients = terminal.command(terminal.source, "list-clients")
    while clients and time.monotonic() < deadline:
        time.sleep(0.05)
        clients = terminal.command(terminal.source, "list-clients")
    assert clients == ""
