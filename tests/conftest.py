from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from config.machine_loader import _reset_caches
from tests.machining_fixtures import write_machining_configuration


@pytest.fixture(autouse=True)
def isolated_machine_configuration(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    shipped = request.node.get_closest_marker("shipped_configuration") is not None
    if shipped:
        monkeypatch.delenv("MILL_UI_MACHINES_DIR", raising=False)
    else:
        monkeypatch.setenv("MILL_UI_MACHINES_DIR", str(tmp_path_factory.mktemp("machine_configuration")))
    _reset_caches()
    try:
        yield
    finally:
        _reset_caches()


@pytest.fixture
def machining_config(isolated_machine_configuration: None) -> Path:
    return write_machining_configuration(Path(os.environ["MILL_UI_MACHINES_DIR"]))
