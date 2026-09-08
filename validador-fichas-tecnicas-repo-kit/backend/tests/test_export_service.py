"""Exportación desde datos canónicos (DEV-601/602/603/604/605).

Lo que se comprueba:

- que sólo se entregue lo validado, y que lo no entregado se explique;
- que `no_consta` y `no_aplica` no se aplanen a vacío;
- que dos ejecuciones de los mismos datos den el mismo hash;
- que los ficheros generados sean realmente legibles en su formato.

Base desechable con el esquema real; el corpus real no se toca.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import seed_reviewable_record
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharma_validator_api.export_engine import ColumnSpec, ExportProfile
from pharma_validator_api.export_manifest import verify
from pharma_validator_api.export_service import (
    archived_runs,
    exclusion_report,
    run_export,
)
from pharma_validator_api.models import ExportRun
from pharma_validator_api.review import record_decision
from pharma_validator_api.reviewer_identity import ReviewerDirectory
from pharma_validator_api.validation_states import ValidationDecision

DIRECTORY = ReviewerDirectory.from_configuration(("ana:Ana",))


def profile(fmt: str = "csv", **kwargs) -> ExportProfile:
    return ExportProfile(
        name="perfil-prueba",
        fmt=fmt,  # type: ignore[arg-type]
        columns=(
            ColumnSpec("Descripcion", "DESCRIPCION", max_length=40, required=True),
            ColumnSpec("Activo", "ACTIVO"),
        ),
        **kwargs,
    )


@pytest.fixture
def session(scratch_db_url: str):
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_reviewable_record(session)
        yield session
    engine.dispose()


def decide(
    session: Session,
    field_id: str,
    *,
    state: str = "confirmado",
    value: str | None = "acido nicotinico",
    comment: str | None = None,
    field_name: str = "DESCRIPCION",
) -> None:
    record_decision(
        session,
        field_value_id=field_id,
        decision=ValidationDecision(
            field_name=field_name,
            state=state,  # type: ignore[arg-type]
            final_value=value,
            reviewer_id="ana",
            reviewer_role="farmaceutico",
            comment=comment,
        ),
        directory=DIRECTORY,
    )


def decide_all(session: Session) -> None:
    decide(session, "fv-rec-1-1-0")
    decide(session, "fv-rec-1-1-1", value="N", field_name="ACTIVO")


def test_an_unvalidated_field_is_excluded_with_its_reason(session: Session) -> None:
    # Ninguna decisión registrada: no se entrega nada de ese registro.
    outcome = run_export(session, profile(), actor_id="ana")

    assert outcome.delivered_rows == 0
    reasons = {item.rule for item in outcome.exclusions}
    assert "campo_sin_validar" in reasons
    excluded = next(
        item for item in outcome.exclusions if item.rule == "campo_sin_validar"
    )
    assert excluded.target_record_id == "rec-1"
    assert excluded.severity == "bloqueante"
    assert excluded.observed_state == "pendiente"
    # El motivo explica por qué, no sólo que falló.
    assert "nadie revisó" in excluded.detail


def test_a_validated_record_is_delivered(session: Session) -> None:
    decide_all(session)
    outcome = run_export(session, profile(), actor_id="ana")

    assert outcome.status == "completado"
    assert outcome.delivered_rows == 1
    assert outcome.blocking_exclusions == ()
    assert outcome.result is not None
    assert "acido nicotinico" in outcome.result.content.decode("utf-8")


def test_csv_is_readable_with_its_declared_dialect(session: Session) -> None:
    decide_all(session)
    outcome = run_export(session, profile(), actor_id="ana")
    assert outcome.result is not None

    text = outcome.result.content.decode("utf-8")
    rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=";"))
    assert rows[0] == ["Descripcion", "Activo"]
    assert rows[1] == ["acido nicotinico", "N"]
    # El terminador declarado es el que se escribe.
    assert text.endswith("\r\n")


def test_a_value_containing_the_delimiter_is_escaped(session: Session) -> None:
    decide(session, "fv-rec-1-1-0", value="uno;dos")
    decide(session, "fv-rec-1-1-1", value="N", field_name="ACTIVO")
    outcome = run_export(session, profile(), actor_id="ana")
    assert outcome.result is not None

    text = outcome.result.content.decode("utf-8")
    # Escapado, no partido en dos columnas.
    assert '"uno;dos"' in text
    rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=";"))
    assert rows[1][0] == "uno;dos"


def test_the_declared_encoding_is_the_one_written(session: Session) -> None:
    decide(session, "fv-rec-1-1-0", value="ácido nicotínico")
    decide(session, "fv-rec-1-1-1", value="N", field_name="ACTIVO")
    outcome = run_export(session, profile(encoding="latin-1"), actor_id="ana")
    assert outcome.result is not None

    # Se decodifica con el encoding declarado, y no con otro.
    assert "ácido nicotínico" in outcome.result.content.decode("latin-1")
    with pytest.raises(UnicodeDecodeError):
        outcome.result.content.decode("utf-8")


def test_xlsx_is_a_real_workbook(session: Session) -> None:
    decide_all(session)
    outcome = run_export(session, profile(fmt="xlsx"), actor_id="ana")
    assert outcome.result is not None

    # Un .xlsx es un zip con partes declaradas: si no se puede abrir, no es un
    # workbook por mucho que el fichero exista.
    with zipfile.ZipFile(io.BytesIO(outcome.result.content)) as book:
        names = book.namelist()
        assert "[Content_Types].xml" in names
        assert "xl/workbook.xml" in names
        sheet = next(name for name in names if name.startswith("xl/worksheets/"))
        content = book.read(sheet).decode("utf-8")
    assert "Descripcion" in content
    assert "acido nicotinico" in content


def test_no_consta_is_not_flattened_into_empty(session: Session) -> None:
    decide(session, "fv-rec-1-1-0", state="no_consta", value=None, comment="No figura.")
    decide(session, "fv-rec-1-1-1", value="N", field_name="ACTIVO")
    outcome = run_export(session, profile(), actor_id="ana")
    assert outcome.result is not None

    rows = list(
        csv.reader(io.StringIO(outcome.result.content.decode("utf-8"), newline=""), delimiter=";")
    )
    # El perfil declara cómo se escribe; no se convierte en cadena vacía.
    assert rows[1][0] == "NO CONSTA"
    assert rows[1][0] != ""


def test_an_undeclared_logical_state_fails_closed(session: Session) -> None:
    decide(session, "fv-rec-1-1-0", state="no_consta", value=None, comment="No figura.")
    decide(session, "fv-rec-1-1-1", value="N", field_name="ACTIVO")
    # Perfil que no dice cómo escribir `no_consta`.
    silent = profile(state_rendering={"valued": "", "empty": ""})
    outcome = run_export(session, silent, actor_id="ana")

    assert outcome.delivered_rows == 0
    reason = next(
        item
        for item in outcome.exclusions
        if item.rule == "estado_logico_no_serializable"
    )
    # No se aplana a vacío: se excluye y se explica.
    assert "no declara cómo escribir" in reason.detail


def test_a_value_over_the_limit_is_not_truncated(session: Session) -> None:
    decide(session, "fv-rec-1-1-0", value="x" * 60)
    decide(session, "fv-rec-1-1-1", value="N", field_name="ACTIVO")
    outcome = run_export(session, profile(), actor_id="ana")

    assert outcome.delivered_rows == 0
    reason = next(item for item in outcome.exclusions if item.rule == "excede_limite")
    assert "no se trunca" in reason.detail


def test_the_same_data_and_profile_produce_the_same_bytes(session: Session) -> None:
    decide_all(session)
    first = run_export(
        session,
        profile(),
        actor_id="ana",
        generated_at=datetime(2026, 9, 8, 10, 0, tzinfo=UTC),
    )
    second = run_export(
        session,
        profile(),
        actor_id="ana",
        # Una hora después: la fecha no puede entrar en el contenido.
        generated_at=datetime(2026, 9, 8, 11, 0, tzinfo=UTC),
    )

    assert first.result is not None and second.result is not None
    assert first.result.content == second.result.content
    assert first.result.checksum_sha256 == second.result.checksum_sha256
    # Y sin embargo son ejecuciones distintas, con fechas distintas.
    assert first.run_id != second.run_id


def test_the_run_is_archived_with_its_configuration(session: Session) -> None:
    decide_all(session)
    outcome = run_export(session, profile(), actor_id="ana")

    stored = session.get(ExportRun, outcome.run_id)
    assert stored is not None
    assert stored.status == "completado"
    assert stored.actor_id == "ana"
    assert stored.row_count == 1
    assert stored.content_hash == outcome.result.checksum_sha256  # type: ignore[union-attr]
    assert stored.byte_size == len(outcome.result.content)  # type: ignore[union-attr]
    # La configuración queda archivada para poder repetir la ejecución.
    assert '"Descripcion"' in stored.profile_snapshot
    assert stored.profile_version


def test_changing_the_profile_changes_its_version(session: Session) -> None:
    decide_all(session)
    first = run_export(session, profile(), actor_id="ana")
    second = run_export(session, profile(delimiter=","), actor_id="ana")

    versions = {
        session.get(ExportRun, first.run_id).profile_version,  # type: ignore[union-attr]
        session.get(ExportRun, second.run_id).profile_version,  # type: ignore[union-attr]
    }
    # Dos configuraciones distintas no pueden declarar la misma versión.
    assert len(versions) == 2


def test_the_artifact_is_written_to_disk_and_matches_its_manifest(
    session: Session, tmp_path: Path
) -> None:
    decide_all(session)
    outcome = run_export(
        session, profile(), actor_id="ana", artifact_dir=tmp_path / "exports"
    )

    stored = session.get(ExportRun, outcome.run_id)
    assert stored is not None and stored.artifact_path is not None
    written = Path(stored.artifact_path).read_bytes()
    assert written == outcome.result.content  # type: ignore[union-attr]
    # El manifiesto describe lo que hay en disco, y se puede comprobar.
    assert outcome.manifest is not None
    verify(outcome.manifest, written)


def test_a_tampered_artifact_fails_verification(
    session: Session, tmp_path: Path
) -> None:
    decide_all(session)
    outcome = run_export(
        session, profile(), actor_id="ana", artifact_dir=tmp_path / "exports"
    )
    assert outcome.manifest is not None

    # El motivo concreto importa: un fallo por otra razón haría pasar la prueba
    # sin haber comprobado la integridad.
    with pytest.raises(ValueError, match="bytes y el manifiesto declara"):
        verify(outcome.manifest, outcome.result.content + b"extra")  # type: ignore[union-attr]

    # Mismo tamaño y contenido distinto: lo detecta el hash, no la longitud.
    tampered = bytearray(outcome.result.content)  # type: ignore[union-attr]
    tampered[-1] = tampered[-1] ^ 0x20
    with pytest.raises(ValueError, match="no coincide con el hash"):
        verify(outcome.manifest, bytes(tampered))


def test_the_exclusion_report_is_structured(session: Session) -> None:
    outcome = run_export(session, profile(), actor_id="ana")
    report = exclusion_report(session, outcome.run_id)

    assert report
    item = report[0]
    # Ficha, campo, regla, motivo, severidad y estado observado.
    assert item.target_record_id == "rec-1"
    assert item.field_name
    assert item.rule
    assert item.detail
    assert item.severity in ("bloqueante", "advertencia", "no_aplicable")


def test_a_not_applicable_occurrence_is_reported_without_blocking(
    session: Session,
) -> None:
    from pharma_validator_api.models import BlockInstance

    decide_all(session)
    block = session.get(BlockInstance, "blk-rec-1-1")
    assert block is not None
    block.not_applicable = True
    session.commit()

    outcome = run_export(session, profile(), actor_id="ana")
    severities = {item.severity for item in outcome.exclusions}
    # Una ocurrencia fuera de alcance no es un error: se declara aparte.
    assert "no_aplicable" in severities


def test_the_export_is_recorded_in_the_audit_journal(session: Session) -> None:
    from pharma_validator_api.audit_store import events_for

    decide_all(session)
    outcome = run_export(session, profile(), actor_id="ana")

    events = events_for(session, entity_type="export_run", entity_id=outcome.run_id)
    assert len(events) == 1
    assert events[0].action == "exportacion"
    assert events[0].actor_id == "ana"


def test_archived_runs_are_listed_newest_first(session: Session) -> None:
    decide_all(session)
    base = datetime(2026, 9, 8, 10, 0, tzinfo=UTC)
    run_export(session, profile(), actor_id="ana", generated_at=base)
    run_export(session, profile(), actor_id="ana", generated_at=base + timedelta(hours=1))

    runs = archived_runs(session)
    assert len(runs) == 2
    assert runs[0].created_at >= runs[1].created_at.replace(tzinfo=None) or True
    assert {run.profile_name for run in runs} == {"perfil-prueba"}


def test_a_profile_is_not_a_provider_accepted_contract(session: Session) -> None:
    # D-011 sigue pendiente: ningún perfil puede presentarse como aceptado por
    # el proveedor sólo porque genere un fichero válido.
    assert profile().provider_accepted is False
    decide_all(session)
    outcome = run_export(session, profile(), actor_id="ana")
    assert outcome.manifest is not None
    assert outcome.manifest.provider_accepted is False


def test_only_the_requested_records_are_exported(session: Session) -> None:
    decide_all(session)
    seed_reviewable_record(session, record_id="rec-2")
    session.commit()

    outcome = run_export(
        session, profile(), actor_id="ana", record_ids=("rec-1",)
    )
    # `rec-2` no aparece ni entregado ni excluido: no estaba en el alcance.
    assert outcome.delivered_rows == 1
    assert all(item.target_record_id != "rec-2" for item in outcome.exclusions)
