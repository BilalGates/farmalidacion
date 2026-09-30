"""El ejecutor operativo no crea bases vacías ni consulta en modo DEMO."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts import run_cima_maintenance
from scripts.maintenance_lock import MaintenanceAlreadyRunning, maintenance_lock


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


def test_second_maintenance_runner_fails_until_first_releases_lock(tmp_path: Path) -> None:
    database = tmp_path / "real.db"
    database.touch()
    with (
        maintenance_lock(database),
        pytest.raises(MaintenanceAlreadyRunning, match="Ya hay una pasada CIMA activa"),
        maintenance_lock(database),
    ):
        pass
    with maintenance_lock(database):
        pass


def test_maintenance_lock_releases_after_error(tmp_path: Path) -> None:
    database = tmp_path / "real.db"
    database.touch()
    with pytest.raises(RuntimeError, match="fallo"), maintenance_lock(database):
        raise RuntimeError("fallo")
    with maintenance_lock(database):
        pass


def test_cli_rejects_overlapping_run_before_opening_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "real.db"
    database.touch()
    monkeypatch.setenv("APP_DATA_MODE", "real")
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{database.as_posix()}")
    monkeypatch.setattr(sys, "argv", ["run_cima_maintenance.py", "--start-date", "27/09/2026"])
    with maintenance_lock(database), pytest.raises(SystemExit, match="2"):
        run_cima_maintenance.main()
