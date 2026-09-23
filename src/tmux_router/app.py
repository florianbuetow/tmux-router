"""Connect the session menu to native tmux attachment."""

import curses
import os
import shutil
import sys

from libtmux import Server

from tmux_router.picker import choose, show_message
from tmux_router.proxy import AttachError, attach
from tmux_router.sessions import command, list_sessions


def source_server(binary: str) -> Server:
    """Use the invoking server inside tmux, or tmux's standard server outside."""
    if "TMUX" in os.environ:
        socket = os.environ["TMUX"].rsplit(",", 2)[0]
        if not socket:
            raise RuntimeError("TMUX contains an empty server socket path.")
        return Server(socket_path=socket, tmux_bin=binary)
    return Server(tmux_bin=binary)


def run(binary: str) -> None:
    """Select sessions on the invoking tmux server until interrupted."""
    curses.wrapper(route, binary, source_server(binary))


def route(screen: curses.window, binary: str, server: Server) -> None:
    """Alternate between the menu and native attachment on one curses screen.

    Re-entering curses for every menu repaints the previous menu before the
    fresh one, so the screen stays initialized and is only suspended while a
    native client owns the terminal.
    """
    while True:
        selected = choose(screen, lambda: list_sessions(server))
        if selected.key not in {session.key for session in list_sessions(server)}:
            show_message(screen, "The selected session doesn't exist anymore.")
            continue
        try:
            socket = command(server, "display-message", "-p", "-t", selected.identity, "#{socket_path}")[0]
            if "TMUX_PANE" in os.environ and "TMUX" in os.environ:
                current = command(server, "display-message", "-p", "-t", os.environ["TMUX_PANE"], "#{session_id}")[0]
                if current == selected.identity:
                    show_message(screen, "This session contains the router. Attach from a terminal outside this session.")
                    continue
        except RuntimeError:
            if selected.key in {session.key for session in list_sessions(server)}:
                raise
            show_message(screen, "The selected session doesn't exist anymore.")
            continue
        curses.endwin()
        try:
            attach(binary, socket, selected)
        except AttachError:
            if selected.key in {session.key for session in list_sessions(server)}:
                raise
            show_message(screen, "The selected session doesn't exist anymore.")


def main() -> int:
    """Run the interactive application and restore the terminal on exit."""
    try:
        binary = shutil.which("tmux")
        if binary is None:
            raise RuntimeError("tmux is required but was not found on PATH.")
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise RuntimeError("tmux-router requires an interactive terminal.")
        if "TERM" not in os.environ or not os.environ["TERM"]:
            raise RuntimeError("TERM must identify the interactive terminal.")
        run(binary)
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, OSError, curses.error) as error:
        print(f"tmux-router: {error}", file=sys.stderr)
        return 1
    return 0
