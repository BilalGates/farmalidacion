"""Construye el informe DEV-511 desde observaciones JSONL verificadas."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "backend" / "src"))

from pharma_validator_api.pilot_reporting import (  # noqa: E402
    PilotObservation,
    PilotReportingError,
    build_pilot_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--expected-records", type=int, default=50)
    arguments = parser.parse_args()
    try:
        rows = []
        for line_number, line in enumerate(
            arguments.input.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            payload = json.loads(line)
            if payload.pop("is_synthetic", False):
                raise PilotReportingError(
                    f"Línea {line_number}: una observación sintética no puede entrar al piloto."
                )
            rows.append(PilotObservation(**payload))
        report = build_pilot_report(
            tuple(rows), expected_records=arguments.expected_records
        )
    except (OSError, json.JSONDecodeError, TypeError, PilotReportingError) as error:
        print(json.dumps({"status": "FAIL", "detail": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
