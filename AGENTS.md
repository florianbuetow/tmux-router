# tmux-router: Purpose and Usage

## What this tool is for

tmux-router is an interactive terminal tool for quickly switching between
existing tmux sessions. It displays a numbered session list, lets you attach by
entering a number, and provides F1 to return to the list without ending the
session or its running programs.

Use it when you have several tmux sessions and want to choose between them
without remembering their names or repeatedly typing attachment commands.
It does not create your working sessions; create those with tmux first.

## Requirements and startup

- macOS or Linux with an interactive terminal.
- Python 3.12 or newer, `uv`, `just`, and `tmux` available on PATH.
- A terminal with a valid `TERM` setting and support for `tmux-256color`.

From the project directory, install the declared dependencies and start:

```sh
uv sync --all-extras
just run
```

For subsequent launches, use `just run`. Alternatively, run the installed
entry point with `uv run tmux-router`.

Launch from a terminal outside the session you want to enter. The router rejects
attachment to the session containing itself because that would create a
recursive terminal view. Input and output must be connected to a terminal;
piping or redirecting them is not supported.

## Choosing a session

The menu lists existing sessions, including detached sessions, in alphabetical
order. Its columns are:

| Column | Meaning |
| --- | --- |
| # | Number to enter to select this session. |
| Session | The tmux session's name. |
| Working directory | The current directory of that session's active pane. |

1. Find the session you want.
2. Type its number into the input below the list.
3. Press Enter to attach.

The list refreshes every 10 seconds while the input is empty. Once you start
typing, refreshing pauses so the displayed numbers cannot change underneath
your selection. Backspace removes a character; Ctrl-U clears the entire input.
Refreshing resumes when the input is empty. Use Up/Down to scroll longer lists.

If the selected session disappears before attachment, the tool displays
"The selected session doesn't exist anymore." Press Enter to return to a fresh
list. Invalid numbers also show a message and wait for Enter. If there are no
sessions, the menu displays "No active sessions." and continues refreshing.

## Working inside a session

Use the attached session normally. Text, Enter, Escape, arrow keys, control
keys, and your existing tmux prefix are passed through. Ctrl-C goes to the
running application while attached.

An additional bottom line displays:

```text
F1: return to sessions | You are currently in session NAME | DIRECTORY
```

The line follows the attached client's current session and active pane, including
native tmux session switches. The directory belongs to the active pane: a session
with several panes has no single shared working directory.

Press **F1** to return to the session list. F1 is reserved by the router and is
not passed to the application. Returning leaves the original session running.
To quit the router, press **Ctrl-C in the session list**. There is deliberately
no exit entry or exit hint in that menu.

## Server scope and terminal behavior

Outside tmux, the tool uses tmux's standard server. Inside tmux, it uses the
server identified by the `TMUX` environment variable. It does not aggregate
sessions from multiple independent tmux servers.

libtmux handles discovery and management commands. Attachment uses a real tmux
client inside a temporary private tmux server, preserving native rendering and
input handling. The wrapper has its own socket and configuration. Cleanup
detaches only the router's client and removes its wrapper; it does not kill
your working sessions or change their configuration.

The extra status line consumes one terminal row. Applications resize to the
remaining area, and the original tmux status bar remains visible if enabled.
Advanced terminal features depend on the terminal and nested tmux support.

Agents operating this tool must allocate an interactive terminal or PTY. Use
F1 to leave a session; do not kill a user's session merely to exit the router.

## Development Rules

This file provides guidance to AI agents and AI-assisted development tools when working with this project. This includes Claude Code, Cursor IDE, GitHub Copilot, Windsurf, and any other AI coding assistants.

## General Coding Principles
- **Do not preserve backward compatibility.** Remove obsolete paths instead of adding compatibility layers, fallbacks, or migrations.
- **Choose the simplest implementation that fully meets the current requirements.** Avoid speculative abstractions, configuration, and indirection.
- **Grow the system in layers.** Start from the smallest version that works end to end, and add each new capability on top of a product that already works. Never trade a working product for unfinished complexity.
- **Keep components modular and concerns clearly separated.**
- **Prefer established, well-maintained libraries when they reduce overall complexity or improve reliability.** Do not reimplement common functionality without a clear reason.
- **Lean on the dependencies already in the project before writing your own implementation or adding packages.** Do not assume a library lacks a capability without checking its documentation and types.
- **Make architectural decisions for the long term.** Do not accept a stopgap that only works for now and is meant to be replaced later.
- **Fail fast — never swallow errors.** Always propagate errors and exit with code 1 immediately. No silent fallbacks, no `|| true`, no ignored return codes.
- **Never assume any default values anywhere.** Check for required values explicitly and exit 1 if something is missing. Default values mask underlying issues and make them hard to debug.
- **Never suppress checks with annotations.** Fix the underlying issue instead. No `# noqa`, `# type: ignore`, `# nosec`, `@pytest.mark.filterwarnings`, or any other mechanism that silences a checker.
- Always be explicit about values, paths, and configurations
- If a value is not provided, raise an error — never silently fall back to a default

## Git Commit Guidelines

**IMPORTANT:** When creating git commits in this repository:
- **NEVER include AI attribution in commit messages**
- **NEVER add "Generated with [AI tool name]" or similar phrases**
- **NEVER add "Co-Authored-By: [AI name]" or similar attribution**
- **NEVER run `git add -A` or `git add .` - always stage files explicitly**
- Keep commit messages professional and focused on the changes made
- Commit messages should describe what changed and why, without mentioning AI assistance
- **Commit only when requested. A request to commit does not authorize a push.**
- **Never push or configure a remote unless the user explicitly requests it.**

## Testing
- After **every change** to the code, the tests must be executed
- Always verify the program runs correctly with `just run` after modifications

## Python Execution Rules
- Python code must be executed **only** via `uv run ...`
  - Example: `uv run src/main.py`
  - **Never** use: `python src/main.py` or `python3 src/main.py`
- The virtual environment must be created and updated **only** via `uv sync`
  - **Never** use: `pip install`, `python -m pip`, or `uv pip`
- All dependencies must be managed through `uv` and declared in `pyproject.toml`

## Justfile Conventions
- **Use `printf` for colored or formatted output** — never `echo` with ANSI escape sequences, as some terminals won't render colors with `echo`. Plain `echo ""` is acceptable only for blank-line spacing.
- **Add an empty `@echo ""` line before and after each target's command block** to visually separate output between targets.
- **The `help` target must be a dedicated recipe** with manually written `printf` lines that group related commands and order them by typical execution flow (setup → run → code quality → testing). Never use `just --list`.
- **The default target (`_default`) must call `just help`.**
- **Every target must end with a clear status message**: green (`\033[32m`) on success, red (`\033[31m`) on failure with `exit 1`.
- **Composite targets (e.g. `ci`) must fail fast**: use `set -e` or `&&` chaining.
- All Python execution in the justfile uses `uv run`, never `python` directly
- Use `just init` to set up the project
- Use `just run` to execute the main program
- Use `just destroy` to remove the virtual environment
- Use `just ci` to run all validation checks (verbose)
- Use `just ci-quiet` to run all validation checks (silent, fail-fast)

## Project Structure
- All source code lives in `src/`
- Test scripts and utilities go in `scripts/`
- **Input data is organized**: `data/input/`
- **Output data is organized**: `data/output/`
- **Never create Python files in the project root directory**
  - Wrong: `./test.py`, `./helper.py`
  - Correct: `./src/helper.py`, `./scripts/test.py`

## Error Handling
- Fail fast — stop immediately on the first error, never continue past failures
- Never catch and silently ignore exceptions
- Raise exceptions with clear messages for missing or invalid data
- Exit with code 1 if any operation fails, 0 if all succeeded

## Optimization
- **Skip processing if output already exists** - Don't reprocess unnecessarily
- Check if output file exists before starting expensive operations
- Track skipped items separately in summary reports
- Allow users to force reprocessing by deleting output files
