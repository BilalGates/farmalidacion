"""Checks for the hosted database handoff scripts using synthetic SQLite data."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "check_hosted_database.py"
SNAPSHOT = ROOT / "scripts" / "prepare_hosted_snapshot.py"


def _database(path: Path, *, demo: bool = False) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE target_record (id TEXT PRIMARY KEY);
            CREATE TABLE source_document (id TEXT PRIMARY KEY, source_type TEXT);
            CREATE TABLE source_document_version (id TEXT PRIMARY KEY, document_id TEXT);
            CREATE TABLE document_record_link (target_record_id TEXT, document_version_id TEXT);
            INSERT INTO target_record VALUES ('record-1');
            """
        )
        if demo:
            connection.executescript(
                """
                INSERT INTO source_document VALUES ('document-1', 'demo_showcase');
                INSERT INTO source_document_version VALUES ('version-1', 'document-1');
                INSERT INTO document_record_link VALUES ('record-1', 'version-1');
                """
            )


def _check(path: Path, minimum: int = 1) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECK), str(path)],
        env={**os.environ, "HOSTED_MIN_REAL_RECORDS": str(minimum)},
        text=True,
        capture_output=True,
        check=False,
    )


def test_hosted_preflight_requires_real_records(tmp_path: Path) -> None:
    database = tmp_path / "real.db"
    _database(database)
    assert _check(database).returncode == 0
    assert _check(database, minimum=2).returncode == 1
    assert _check(tmp_path / "missing.db").returncode == 1


def test_hosted_preflight_rejects_demo(tmp_path: Path) -> None:
    database = tmp_path / "demo.db"
    _database(database, demo=True)
    assert _check(database).returncode == 1


def test_snapshot_is_consistent_and_does_not_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    destination = tmp_path / "hosted" / "real.db"
    _database(source)
    command = [sys.executable, str(SNAPSHOT), str(source), str(destination)]
    assert subprocess.run(command, capture_output=True, check=False).returncode == 0
    assert _check(destination).returncode == 0
    assert subprocess.run(command, capture_output=True, check=False).returncode != 0
