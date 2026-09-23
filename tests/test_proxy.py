"""Tests for wrapper cleanup behavior."""

import signal

import pytest

from tmux_router.proxy import cleanup_on_signals


def test_cleanup_on_signals_lets_cleanup_finish_despite_repeated_signals() -> None:
    steps: list[str] = []

    with pytest.raises(KeyboardInterrupt), cleanup_on_signals():
        try:
            signal.raise_signal(signal.SIGHUP)
            steps.append("not interrupted")
        finally:
            signal.raise_signal(signal.SIGHUP)
            signal.raise_signal(signal.SIGTERM)
            steps.append("cleanup finished")

    assert steps == ["cleanup finished"]
    assert signal.getsignal(signal.SIGHUP) is signal.SIG_DFL
    assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL
