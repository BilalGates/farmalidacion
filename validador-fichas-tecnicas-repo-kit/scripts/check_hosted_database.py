"""Fail closed when a hosted REAL database is missing or contains demo records."""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    database = (Path(sys.argv[1]) if len(sys.argv) == 2 else Path("/app/data/real.db")).resolve()
    minimum = int(os.environ["HOSTED_MIN_REAL_RECORDS"])
    if minimum < 1 or not database.is_file() or database.stat().st_size == 0:
        print("Base REAL ausente o umbral de registros no válido.", file=sys.stderr)
        return 1

    try:
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            total = connection.execute("SELECT COUNT(*) FROM target_record").fetchone()[0]
            demo = connection.execute(
                """SELECT COUNT(DISTINCT l.target_record_id)
                   FROM document_record_link AS l
                   JOIN source_document_version AS v ON v.id = l.document_version_id
                   JOIN source_document AS d ON d.id = v.document_id
                   WHERE d.source_type IN ('demo_showcase', 'synthetic_fixture')"""
            ).fetchone()[0]
    except sqlite3.Error as exc:
        print(f"No se puede comprobar la base REAL: {exc}", file=sys.stderr)
        return 1

    if total < minimum or demo:
        print(
            f"Base REAL no apta: {total} registros, {demo} DEMO; mínimo {minimum}.",
            file=sys.stderr,
        )
        return 1
    print(f"Base REAL comprobada: {total} registros, 0 DEMO.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
