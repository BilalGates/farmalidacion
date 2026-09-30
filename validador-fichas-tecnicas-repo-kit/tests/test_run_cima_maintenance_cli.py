"""El ejecutor operativo no crea bases vacías ni consulta en modo DEMO."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts import run_cima_maintenance


def test_rejects_demo_mode_before_connecting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DATA_MODE", "demo")
    monkeypatch.setattr(sys, "argv", ["run_cima_maintenance.py", "--start-date", "27/09/2026"])

    with pytest.raises(SystemExit, match="2"):
        run_cima_maintenance.main()


def test_rejects_missing_real_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing.db"
    monkeypatch.setenv("APP_DATA_MODE", "real")
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{missing.as_posix()}")
    monkeypatch.setattr(sys, "argv", ["run_cima_maintenance.py", "--start-date", "27/09/2026"])

    with pytest.raises(SystemExit, match="2"):
        run_cima_maintenance.main()
    assert not missing.exists()
