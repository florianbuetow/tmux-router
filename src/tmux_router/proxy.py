"""Use a private tmux wrapper to preserve native terminal rendering and input."""

import os
import shlex
import signal
import subprocess
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import FrameType

from libtmux import Server

from tmux_router.sessions import Session, command, list_sessions


class AttachError(RuntimeError):
    """The inner client failed to attach to the original session."""


@contextmanager
def cleanup_on_signals() -> Generator[None]:
    """Unwind the wrapper when the hosting terminal closes or terminates us."""
    unwinding = False

    def interrupt(signum: int, frame: FrameType | None) -> None:
        """Start exception cleanup once; a closing terminal repeats the signal."""
        nonlocal unwinding
        if unwinding:
            return
        unwinding = True
        raise KeyboardInterrupt

    previous = {number: signal.signal(number, interrupt) for number in (signal.SIGHUP, signal.SIGTERM)}
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def proxy_config(binary: str, socket: str) -> str:
    """Build an isolated configuration with a live source-session status line."""
    status_command = shlex.join(
        [
            binary,
            "-S",
            socket,
            "display-message",
            "-p",
            "-c",
            "#{pane_tty}",
            "You are currently in session ##{session_name} | ##{pane_current_path}",
        ]
    )
    status = "#[reverse] F1: return to sessions | #(" + status_command + ")"
    return "\n".join(
        [
            "set -g prefix None",
            "set -g prefix2 None",
            "set -g mouse off",
            "set -s extended-keys on",
            "set -s focus-events on",
            "set -g status on",
            "set -g status-position bottom",
            "set -g status-interval 1",
            "set -g default-terminal tmux-256color",
            "set -g allow-passthrough on",
            "set -g exit-empty off",
            "set -g remain-on-exit on",
            "set -g status-format[0] " + shlex.quote(status),
            "",
        ]
    )


def detach_inner(server: Server, tty: str) -> None:
    """Detach only our source client, including when its terminal was closed."""
    if not list_sessions(server):
        return
    clients = command(server, "list-clients", "-F", "#{client_name}")
    if tty in clients:
        result = server.cmd("detach-client", "-t", tty)
        if result.returncode != 0 and list_sessions(server) and tty in command(server, "list-clients", "-F", "#{client_name}"):
            raise RuntimeError("\n".join(result.stderr))


def attach(binary: str, socket: str, selected: Session) -> None:
    """Attach a native client, reserving F1 in a disposable wrapper server."""
    with cleanup_on_signals(), TemporaryDirectory(prefix="tmux-router-") as directory:
        config = Path(directory) / "tmux.conf"
        config.write_text(proxy_config(binary, socket))
        proxy_socket = str(Path(directory) / "socket")
        wrapper = Server(socket_path=proxy_socket, config_file=str(config), tmux_bin=binary)
        size = os.get_terminal_size()
        environment = dict(os.environ)
        environment.pop("TMUX", None)
        # The inner client must attach, even when the router itself runs in tmux.
        inner_command = shlex.join(["env", "-u", "TMUX", binary, "-S", socket, "attach-session", "-t", selected.identity])
        command(wrapper, "new-session", "-d", "-s", "router", "-x", str(size.columns), "-y", str(size.lines), inner_command)
        try:
            command(wrapper, "unbind-key", "-a", "-T", "root")
            command(wrapper, "bind-key", "-T", "root", "F1", "detach-client")
            # A dead inner client returns to the picker; unexpected exit codes fail fast.
            command(wrapper, "set-hook", "-g", "pane-died", "detach-client -s router")
            result = subprocess.run(
                [binary, "-S", proxy_socket, "attach-session", "-t", "router", ";", "if-shell", "-F", "#{pane_dead}", "detach-client"],
                env=environment,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(f"tmux proxy client exited with status {result.returncode}")
            pane = command(wrapper, "display-message", "-p", "#{pane_dead}\t#{pane_dead_status}")
            if pane and pane[0].startswith("1\t") and pane[0] != "1\t0":
                raise AttachError(f"tmux attach failed (exit {pane[0].split(chr(9))[1]}).")
        finally:
            try:
                tty = command(wrapper, "display-message", "-p", "#{pane_tty}")[0]
                detach_inner(Server(socket_path=socket, tmux_bin=binary), tty)
            finally:
                command(wrapper, "kill-server")
