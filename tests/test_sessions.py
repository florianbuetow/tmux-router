"""Tests for tmux session discovery."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tmux_router.sessions import Session, command, list_sessions


def result(returncode: int, stdout: list[str] | None = None, stderr: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=[] if stdout is None else stdout, stderr=[] if stderr is None else stderr)


def test_list_sessions_sorts_names_alphabetically_and_preserves_metadata() -> None:
    server = Mock()
    server.cmd.return_value = result(
        0,
        [
            "$3\tzulu\t4103\t1788800003\t/work/zulu",
            "$2\tAlpha\t4102\t1788800002\t/work/alpha-upper",
            "$1\talpha\t4101\t1788800001\t/work/alpha-lower",
            "$4\tbravo\t4104\t1788800004\t/work/bravo",
        ],
    )

    assert list_sessions(server) == [
        Session("$2", "Alpha", "/work/alpha-upper", "4102", "1788800002"),
        Session("$1", "alpha", "/work/alpha-lower", "4101", "1788800001"),
        Session("$4", "bravo", "/work/bravo", "4104", "1788800004"),
        Session("$3", "zulu", "/work/zulu", "4103", "1788800003"),
    ]
    server.cmd.assert_called_once_with(
        "list-sessions",
        "-F",
        "#{session_id}\t#{session_name}\t#{pid}\t#{session_created}\t#{pane_current_path}",
    )


def test_session_key_distinguishes_a_recreated_server_reusing_a_session_id() -> None:
    original = Session("$1", "build", "/work/build", "4101", "1788800001")
    recreated = Session("$1", "build", "/work/build", "9204", "1788800100")

    assert original.key == ("$1", "4101", "1788800001")
    assert recreated.key == ("$1", "9204", "1788800100")
    assert original.key != recreated.key


@pytest.mark.parametrize(
    "message",
    [
        "no server running on /private/tmp/tmux-501/default",
        "error connecting to /private/tmp/tmux-501/default (No such file or directory)",
    ],
)
def test_list_sessions_treats_missing_tmux_server_as_an_empty_list(message: str) -> None:
    server = Mock()
    server.cmd.return_value = result(1, stderr=[message])

    assert list_sessions(server) == []


def test_list_sessions_propagates_permission_errors() -> None:
    server = Mock()
    server.cmd.return_value = result(1, stderr=["error connecting to /tmp/tmux/default (Permission denied)"])

    with pytest.raises(RuntimeError, match="Permission denied"):
        list_sessions(server)


def test_command_returns_stdout_on_success() -> None:
    server = Mock()
    server.cmd.return_value = result(0, stdout=["one", "two"])

    assert command(server, "display-message", "-p", "#{session_name}") == ["one", "two"]


def test_command_propagates_tmux_failure_with_all_error_lines() -> None:
    server = Mock()
    server.cmd.return_value = result(1, stderr=["first error", "second error"])

    with pytest.raises(RuntimeError, match="first error\nsecond error"):
        command(server, "attach-session", "-t", "$1")
