"""Exclusión entre ejecutores CIMA que comparten una base SQLite local."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from typing import BinaryIO


class MaintenanceAlreadyRunning(RuntimeError):
    pass


def _lock(file: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        file.seek(0)
        try:
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise MaintenanceAlreadyRunning("Ya hay una pasada CIMA activa para esta base.") from error
    else:
        fcntl = import_module("fcntl")

        try:
            fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise MaintenanceAlreadyRunning("Ya hay una pasada CIMA activa para esta base.") from error


def _unlock(file: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl = import_module("fcntl")

        fcntl.flock(file.fileno(), fcntl.LOCK_UN)


@contextmanager
def maintenance_lock(database_path: Path) -> Iterator[None]:
    lock_path = database_path.with_name(database_path.name + ".cima.lock")
    with lock_path.open("a+b") as file:
        # Windows bloquea un rango de bytes; el fichero permanece en disco y
        # el bloqueo del sistema operativo se libera al terminar el proceso.
        if file.seek(0, os.SEEK_END) == 0:
            file.write(b"\0")
            file.flush()
        _lock(file)
        try:
            yield
        finally:
            _unlock(file)
