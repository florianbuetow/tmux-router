"""Tests for application startup."""

from collections.abc import Callable
from unittest.mock import patch

import pytest

from tmux_router.app import main
from tmux_router.sessions import Session


def test_requires_terminal(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("tmux_router.app.shutil.which", return_value="/usr/bin/tmux"), patch("sys.stdin.isatty", return_value=False):
        assert main() == 1
    assert "requires an interactive terminal" in capsys.readouterr().err


def test_requires_tmux(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("tmux_router.app.shutil.which", return_value=None):
        assert main() == 1
    assert "tmux is required" in capsys.readouterr().err


def test_session_disappearing_during_socket_lookup_returns_to_picker() -> None:
    selected = Session("$1", "alpha", "/work/alpha", "4101", "1788800001")
    shown_messages: list[str] = []

    def wrapper(function: Callable[..., object], *arguments: object) -> object:
        return function(object(), *arguments)

    def choose(screen: object, fetch: object) -> Session:
        if not shown_messages:
            return selected
        raise KeyboardInterrupt

    def show_message(screen: object, message: str) -> None:
        shown_messages.append(message)

    with (
        patch("tmux_router.app.Server"),
        patch("tmux_router.app.curses.wrapper", side_effect=wrapper),
        patch("tmux_router.app.choose", side_effect=choose),
        patch("tmux_router.app.show_message", side_effect=show_message),
        patch("tmux_router.app.list_sessions", side_effect=[[selected], []]),
        patch("tmux_router.app.command", side_effect=RuntimeError("no server running")),
        patch("tmux_router.app.shutil.which", return_value="/usr/bin/tmux"),
        patch("sys.stdin.isatty", return_value=True),
        patch("sys.stdout.isatty", return_value=True),
        patch.dict("tmux_router.app.os.environ", {"TERM": "xterm-256color"}, clear=True),
    ):
        assert main() == 0

    assert shown_messages == ["The selected session doesn't exist anymore."]
