"""A curses picker with stable numbering while an input is being edited."""

import curses
import time
import unicodedata
from collections.abc import Callable

from tmux_router.sessions import Session


class Picker:
    """Keep the visible snapshot frozen until the input is empty."""

    def __init__(self, fetch: Callable[[], list[Session]], now: float) -> None:
        self.fetch = fetch
        self.sessions = fetch()
        self.text = ""
        self.refreshed_at = now

    def refresh(self, now: float) -> None:
        """Refresh at ten-second intervals only when there is no input."""
        if not self.text and now - self.refreshed_at >= 10:
            self.sessions = self.fetch()
            self.refreshed_at = now

    def selected(self) -> Session:
        """Resolve the submitted number against the displayed snapshot."""
        if not self.text.isascii() or not self.text.isdecimal() or len(self.text) > 9:
            raise ValueError("Enter a valid session number.")
        number = int(self.text)
        if not 1 <= number <= len(self.sessions):
            raise ValueError("Enter a valid session number.")
        return self.sessions[number - 1]


def write_line(screen: curses.window, row: int, text: str) -> None:
    """Render printable text clipped to the available terminal width."""
    height, width = screen.getmaxyx()
    if row < height and width > 1:
        safe = "".join(character if character.isprintable() else "?" for character in text)
        columns = 0
        clipped = ""
        for character in safe:
            columns += character_width(character)
            if columns >= width:
                break
            clipped += character
        screen.addstr(row, 0, clipped)


def show_message(screen: curses.window, message: str) -> None:
    """Wait for Enter before returning from a recoverable selection error."""
    while True:
        screen.erase()
        write_line(screen, 0, message)
        write_line(screen, 2, "Press Enter to continue.")
        screen.refresh()
        if screen.getch() in (10, 13, curses.KEY_ENTER):
            return


def character_width(character: str) -> int:
    """Measure the terminal columns occupied by one character."""
    if unicodedata.combining(character):
        return 0
    if unicodedata.east_asian_width(character) in ("W", "F"):
        return 2
    return 1


def display_width(text: str) -> int:
    """Measure terminal columns, including wide and combining characters."""
    return sum(character_width(character) for character in text)


def draw(screen: curses.window, picker: Picker, offset: int) -> None:
    """Draw the session list above a fixed input field."""
    screen.erase()
    height, _ = screen.getmaxyx()
    write_line(screen, 0, "Active tmux sessions")
    number_width = len(str(len(picker.sessions))) + 1
    name_width = max([len("Session"), *(display_width(session.name) for session in picker.sessions)])
    write_line(screen, 1, f"{'#':<{number_width}} {'Session':<{name_width}}  Working directory")
    visible = max(0, height - 5)
    for index, session in enumerate(picker.sessions[offset : offset + visible], offset + 1):
        name = session.name + " " * (name_width - display_width(session.name))
        write_line(screen, index - offset + 1, f"{str(index) + '.':<{number_width}} {name}  {session.directory}")
    if not picker.sessions:
        write_line(screen, 2, "No active sessions.")
    elif len(picker.sessions) > visible:
        write_line(screen, max(0, height - 3), "Up/Down: scroll sessions")
    write_line(screen, max(0, height - 2), "Enter the number of the session you would like to attach to:")
    write_line(screen, height - 1, "> " + picker.text)
    screen.refresh()


def edit(picker: Picker, key: int) -> None:
    """Apply input edits, including clearing with Control-U."""
    if key in (curses.KEY_BACKSPACE, 127, 8):
        picker.text = picker.text[:-1]
    elif key == 21:
        picker.text = ""
    elif 32 <= key <= 126:
        picker.text += chr(key)


def choose(screen: curses.window, fetch: Callable[[], list[Session]]) -> Session:
    """Run the picker until a valid displayed session is selected."""
    screen.timeout(100)
    picker = Picker(fetch, time.monotonic())
    offset = 0
    while True:
        picker.refresh(time.monotonic())
        offset = min(offset, max(0, len(picker.sessions) - max(1, screen.getmaxyx()[0] - 5)))
        draw(screen, picker, offset)
        key = screen.getch()
        if key in (10, 13, curses.KEY_ENTER):
            try:
                return picker.selected()
            except ValueError as error:
                show_message(screen, str(error))
                picker.text = ""
        elif key in (curses.KEY_UP, curses.KEY_DOWN):
            offset = max(0, offset + (1 if key == curses.KEY_DOWN else -1))
        else:
            edit(picker, key)
