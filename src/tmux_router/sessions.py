"""Read session snapshots through libtmux without hiding server failures."""

from dataclasses import dataclass

from libtmux import Server


@dataclass(frozen=True)
class Session:
    """Stable identity and display metadata from one tmux snapshot."""

    identity: str
    name: str
    directory: str
    server_pid: str
    created: str

    @property
    def key(self) -> tuple[str, str, str]:
        """Distinguish session IDs reused after a server restart."""
        return self.identity, self.server_pid, self.created


def command(server: Server, *arguments: str) -> list[str]:
    """Execute a tmux command and propagate failures."""
    result = server.cmd(*arguments)
    if result.returncode != 0 or result.stderr:
        raise RuntimeError("\n".join(result.stderr))
    return result.stdout


def list_sessions(server: Server) -> list[Session]:
    """Return alphabetically numbered candidates, including detached sessions."""
    result = server.cmd("list-sessions", "-F", "#{session_id}\t#{session_name}\t#{pid}\t#{session_created}\t#{pane_current_path}")
    if result.returncode != 0:
        error = "\n".join(result.stderr)
        if error.startswith("no server running on ") or (
            error.startswith("error connecting to ") and error.endswith("(No such file or directory)")
        ):
            return []
        raise RuntimeError(error)
    sessions: list[Session] = []
    for row in result.stdout:
        identity, name, server_pid, created, directory = row.split("\t", 4)
        sessions.append(Session(identity, name, directory, server_pid, created))
    return sorted(sessions, key=lambda session: (session.name.casefold(), session.name))
