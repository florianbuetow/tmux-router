"""Architecture test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestarch import EvaluableArchitecture, get_evaluable_architecture

# Resolve paths relative to this file:
#   tests/architecture/conftest.py -> tests/ -> project root
_TESTS_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _TESTS_DIR.parent
_PACKAGE_DIR = _PROJECT_ROOT / "src" / "tmux_router"


@pytest.fixture(scope="session")
def evaluable() -> EvaluableArchitecture:
    """Build the evaluable architecture graph for tmux_router.

    Uses tmux_router package as both root and module path
    so module names resolve cleanly (e.g. 'tmux_router.module').
    """
    return get_evaluable_architecture(str(_PACKAGE_DIR), str(_PACKAGE_DIR))
