"""Create a consistent, separate SQLite snapshot for a hosted REAL deployment."""

from __future__ import annotations

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    destination = args.destination.resolve()
    if not source.is_file() or destination.exists():
        parser.error("El origen debe existir y el destino debe ser nuevo.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(destination.name + ".part")
    if staging.exists():
        parser.error(f"Existe una copia incompleta: {staging}")

    try:
        with (
            closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original,
            closing(sqlite3.connect(staging)) as copy,
        ):
            original.backup(copy, pages=1000)
            result = copy.execute("PRAGMA quick_check").fetchone()[0]
            if result != "ok":
                raise RuntimeError(f"La copia SQLite no supera quick_check: {result}")
        staging.replace(destination)
    except BaseException:
        staging.unlink(missing_ok=True)
        raise
    print(f"Instantánea íntegra creada: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
