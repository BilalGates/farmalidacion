"""Diagnostica o aplica la proyección conservadora al catálogo tipado."""

from __future__ import annotations

import argparse
import json
from collections import Counter

from pharma_validator_api.catalog_projection import project_target_records
from pharma_validator_api.config import Settings
from pharma_validator_api.database import create_database_engine, create_session_factory


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Proyecta registros importados al catálogo tipado; por defecto no escribe."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Materializa únicamente identidades y relaciones no ambiguas.",
    )
    args = parser.parse_args()
    engine = create_database_engine(Settings())
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            report = project_target_records(session, apply=args.apply)
            if args.apply:
                session.commit()
            diagnostic_counts = Counter(item.code for item in report.diagnostics)
            print(
                json.dumps(
                    {
                        "mode": "apply" if args.apply else "dry-run",
                        "inspected_records": report.inspected_records,
                        "projectable_identities": report.projectable_identities,
                        "created_identities": report.created_identities,
                        "existing_identities": report.existing_identities,
                        "projectable_relations": report.projectable_relations,
                        "created_relations": report.created_relations,
                        "existing_relations": report.existing_relations,
                        "diagnostics": dict(sorted(diagnostic_counts.items())),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
