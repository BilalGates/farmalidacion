from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

BACKEND = Path(__file__).resolve().parents[1]
PREVIOUS = "b0c1d2e3f4a5"
TABLES = {"maintenance_action", "maintenance_action_decision"}


def config(path: Path) -> Config:
    result = Config(str(BACKEND / "alembic.ini"))
    result.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    return result


def test_upgrade_and_downgrade_keep_existing_events(tmp_path: Path) -> None:
    path = tmp_path / "actions.db"
    command.upgrade(config(path), PREVIOUS)
    engine = sa.create_engine(f"sqlite:///{path.as_posix()}")
    assert not TABLES & set(sa.inspect(engine).get_table_names())
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO maintenance_change_event (id, nregistro, occurred_at_epoch, "
            "change_type, areas_json, source_sha256, fetched_at, affected_field_count, "
            "recorded_at) VALUES (:id, '9001', 1, 3, '[\"estado\"]', :sha, 'x', 0, :now)"
        ), {"id": "e" * 64, "sha": "b" * 64, "now": datetime.now(UTC)})

    command.upgrade(config(path), "head")
    inspector = sa.inspect(engine)
    assert set(inspector.get_table_names()) >= TABLES
    columns = {c["name"] for c in inspector.get_columns("maintenance_action")}
    assert {"event_id", "kind", "data_origin", "cima_version_id", "proposed_value",
            "rule_id", "proposal_json", "derivation_version"} <= columns
    indexed = {tuple(i["column_names"]) for i in inspector.get_indexes("maintenance_action")}
    assert {("event_id",), ("target_record_id",), ("identity_id",),
            ("data_origin", "kind")} <= indexed

    command.downgrade(config(path), PREVIOUS)
    inspector = sa.inspect(engine)
    assert not TABLES & set(inspector.get_table_names())
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT count(*) FROM maintenance_change_event")) == 1
    engine.dispose()
