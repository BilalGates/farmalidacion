"""Materializa enlaces CIMA por CN literal exacto sobre la base configurada."""

from __future__ import annotations

import json

from pharma_validator_api.cima_linking import link_cima_to_master
from pharma_validator_api.config import Settings
from pharma_validator_api.database import create_database_engine, create_session_factory


def main() -> int:
    engine = create_database_engine(Settings())
    factory = create_session_factory(engine)
    with factory() as session:
        result = link_cima_to_master(session)
    engine.dispose()
    print(json.dumps(result.__dict__, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
