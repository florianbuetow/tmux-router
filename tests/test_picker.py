"""Tests for picker snapshot and input behavior."""

import curses

import pytest

from tmux_router.picker import Picker, display_width, edit
from tmux_router.sessions import Session


def session(name: str) -> Session:
    return Session(f"${name}", name, f"/work/{name}", "4100", "1788800000")


def test_refreshes_snapshot_after_ten_seconds() -> None:
    snapshots = [[session("alpha")], [session("bravo")]]
    fetch_count = 0

    def fetch() -> list[Session]:
        nonlocal fetch_count
        snapshot = snapshots[fetch_count]
        fetch_count += 1
        return snapshot

    picker = Picker(fetch, now=5.0)

    picker.refresh(14.99)
    assert picker.sessions == [session("alpha")]
    assert fetch_count == 1

    picker.refresh(15.0)
    assert picker.sessions == [session("bravo")]
    assert fetch_count == 2


def test_refresh_pauses_while_text_is_present_and_resumes_when_cleared() -> None:
    snapshots = [[session("alpha")], [session("bravo")]]
    fetch_count = 0

    def fetch() -> list[Session]:
        nonlocal fetch_count
        snapshot = snapshots[fetch_count]
        fetch_count += 1
        return snapshot

    picker = Picker(fetch, now=0.0)
    picker.text = "1"

    picker.refresh(30.0)
    assert picker.sessions == [session("alpha")]
    assert fetch_count == 1

    picker.text = ""
    picker.refresh(30.0)
    assert picker.sessions == [session("bravo")]
    assert fetch_count == 2
    assert picker.refreshed_at == 30.0


def test_selected_uses_the_numbered_snapshot_even_if_backend_session_disappears() -> None:
    backend = [session("alpha"), session("bravo")]
    picker = Picker(lambda: list(backend), now=0.0)
    picker.text = "2"

    backend.clear()

    assert picker.selected() == session("bravo")


@pytest.mark.parametrize("text", ["", "0", "3", "-1", "1.0", "one", "１２", "1234567890"])
def test_selected_rejects_invalid_session_numbers(text: str) -> None:
    picker = Picker(lambda: [session("alpha"), session("bravo")], now=0.0)
    picker.text = text

    with pytest.raises(ValueError, match="Enter a valid session number"):
        picker.selected()


def test_edit_appends_printable_input_and_supports_backspace_variants() -> None:
    picker = Picker(lambda: [], now=0.0)

    edit(picker, ord("1"))
    edit(picker, ord("2"))
    assert picker.text == "12"

    for key in (curses.KEY_BACKSPACE, 127, 8):
        picker.text = "12"
        edit(picker, key)
        assert picker.text == "1"


def test_edit_control_u_clears_input() -> None:
    picker = Picker(lambda: [], now=0.0)
    picker.text = "123"

    edit(picker, 21)

    assert picker.text == ""


@pytest.mark.parametrize(
    ("text", "width"),
    [
        ("", 0),
        ("alpha", 5),
        ("日本語", 6),
        ("e\u0301", 1),
        ("ｗide", 5),
    ],
)
def test_display_width_counts_terminal_columns(text: str, width: int) -> None:
    assert display_width(text) == width
