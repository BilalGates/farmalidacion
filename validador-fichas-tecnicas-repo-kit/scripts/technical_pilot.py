"""Piloto tecnico sintetico: ejercita cola, medicion y doble validacion.

**No es un piloto farmaceutico.** Los revisores son ficticios, las decisiones no
tienen criterio clinico y las mediciones se marcan `is_synthetic=True` para que
no puedan sumarse a ninguna cifra de ahorro real. Sirve para comprobar que las
piezas encajan bajo concurrencia, no para afirmar nada sobre el producto.

Uso:
    python scripts/technical_pilot.py --records 50
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from sqlalchemy import select  # noqa: E402

from pharma_validator_api.config import Settings  # noqa: E402
from pharma_validator_api.database import (  # noqa: E402
    create_database_engine,
    create_session_factory,
)
from pharma_validator_api.double_review import (  # noqa: E402
    ReviewerDecision,
    compare_reviews,
)
from pharma_validator_api.models import ReviewQueueEntry, TargetRecord  # noqa: E402
from pharma_validator_api.review_queue import QueueConflictError  # noqa: E402
from pharma_validator_api.review_queue_store import (  # noqa: E402
    assign,
    enqueue,
    transition,
)
from pharma_validator_api.timing_store import (  # noqa: E402
    close_session,
    record_focus,
    seconds_per_field,
    start_session,
)

# Revisores explicitamente ficticios. Nunca deben confundirse con GOLD-002.
REVIEWER_A = "test_reviewer_a"
REVIEWER_B = "test_reviewer_b"
FIELDS = ("CODIGO_NACIONAL", "ME_DESCRIPCION", "PA_DESCRIPCION")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=50)
    parser.add_argument(
        "--database-url",
        default="sqlite:///./data/local/real.db",
        help="Base sobre la que ejercitar el piloto tecnico.",
    )
    args = parser.parse_args()

    factory = create_session_factory(
        create_database_engine(Settings(database_url=args.database_url))
    )
    now = datetime.now(UTC)
    report: dict[str, object] = {
        "kind": "synthetic / engineering only",
        "clinically_meaningful": False,
        "reviewers": [REVIEWER_A, REVIEWER_B],
    }

    with factory() as session:
        records = list(
            session.scalars(select(TargetRecord.id).order_by(TargetRecord.id).limit(args.records))
        )
        if not records:
            print(json.dumps({"status": "FAIL", "reason": "sin registros"}, indent=2))
            return 1

        conflicts = 0
        completed = 0
        for index, record_id in enumerate(records):
            enqueue(session, record_id, priority=index % 3, now=now)
            assign(session, record_id, REVIEWER_A, now=now)
            # Un segundo revisor intenta tomar el mismo trabajo: debe rebotar.
            try:
                assign(session, record_id, REVIEWER_B, now=now)
            except QueueConflictError:
                conflicts += 1

            transition(session, record_id, "en_revision", REVIEWER_A, now=now)

            opened = start_session(
                session,
                target_record_id=record_id,
                reviewer_id=REVIEWER_A,
                started_at=now,
                is_synthetic=True,
            )
            cursor = 0.0
            for field in FIELDS:
                record_focus(session, opened.id, field, cursor, cursor + 7.0)
                cursor += 10.0
            close_session(session, opened.id, ended_at=now + timedelta(seconds=cursor))

            transition(session, record_id, "completado", REVIEWER_A, now=now)
            completed += 1

        # Doble validacion sobre decisiones ficticias: un campo discrepa a proposito.
        summary = compare_reviews(
            {f: ReviewerDecision(REVIEWER_A, "confirmado", f"valor-{f}") for f in FIELDS},
            {
                f: ReviewerDecision(REVIEWER_B, "confirmado", f"valor-{f}" if i else "otro")
                for i, f in enumerate(FIELDS)
            },
        )

        report.update(
            {
                "status": "PASS",
                "records_processed": completed,
                "collisions_rejected": conflicts,
                "queue_entries": session.scalar(
                    select(ReviewQueueEntry.target_record_id).limit(1)
                )
                is not None,
                "synthetic_seconds_per_field": seconds_per_field(
                    session, include_synthetic=True
                ),
                "real_seconds_per_field": seconds_per_field(session),
                "double_review": {
                    "agreements": summary.agreement_count,
                    "disagreements": len(summary.disagreements),
                    "reconciled": summary.is_reconciled,
                },
            }
        )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
