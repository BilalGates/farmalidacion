"""Derivación, persistencia, decisiones y backfill de acciones de novedades (ADR-0019)."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from maintenance_actions_support import (
    FakeCima,
    listing,
    seed_catalog_record,
    seed_event,
    seed_master_header,
)
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pharma_validator_api.data_origin import DataOrigin
from pharma_validator_api.document_versions import persist_cima_api_response, reconstruct_artifact
from pharma_validator_api.maintenance_action_decisions import (
    ActionConflict,
    ActionError,
    decide,
    send_to_review,
)
from pharma_validator_api.maintenance_actions import (
    ActionDraft,
    ActionInvariantError,
    backfill_actions,
    current_state,
    derive_actions,
    persist_actions,
)
from pharma_validator_api.models import (
    AuditEvent,
    Base,
    FieldMaintenanceRevision,
    ImmutableHistoryError,
    MaintenanceAction,
    MaintenanceActionDecision,
    MaintenanceChangeEvent,
    MaintenanceChangeEventTarget,
    MaintenanceRun,
    MedicationCatalogIdentity,
    MedicationCatalogRevision,
    ReviewQueueEntry,
    SourceDocumentVersion,
)
from pharma_validator_api.reviewer_identity import Reviewer

ANA = Reviewer(identifier="ana", display_name="Ana Ruiz")
STATE_OK = {"estado": {"aut": 1000}, "comerc": True}
STATE_SUSP = {"estado": {"aut": 1000, "susp": 2000}, "comerc": True}
STATE_REV = {"estado": {"aut": 1000, "rev": 3000}, "comerc": False}


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{(tmp_path / 'actions.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as opened:
        seed_catalog_record(opened)
        yield opened
    engine.dispose()


def derive(session: Session, event: MaintenanceChangeEvent, client: FakeCima,
           **kwargs: object) -> list[ActionDraft]:
    targets = session.scalars(
        select(MaintenanceChangeEventTarget).where(
            MaintenanceChangeEventTarget.event_id == event.id
        )
    ).all()
    return derive_actions(
        session, event=event, targets=targets, client=client,  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


def by_kind(drafts: list[ActionDraft]) -> dict[str, ActionDraft]:
    return {draft.kind: draft for draft in drafts}


def test_derive_actions_estado_comerc(session: Session) -> None:
    event = seed_event(session, areas=["estado", "comerc"])
    drafts = by_kind(derive(session, event, FakeCima(states={"600000": STATE_SUSP})))

    assert set(drafts) == {"revisar_estado", "revisar_comercializacion"}
    for draft in drafts.values():
        assert draft.cima_version_id is not None
        assert draft.proposed_value is None and draft.rule_id is None
        assert draft.diagnostic_code == "sin_correspondencia"
        assert draft.master_field_name == "ACTIVO" and draft.master_value_literal == "S"
        assert draft.data_origin == "real"
    assert drafts["revisar_estado"].cima_pointer == "/estado"
    assert drafts["revisar_comercializacion"].cima_pointer == "/comerc"
    assert drafts["revisar_comercializacion"].cima_value_literal == "true"


def test_derive_actions_baja(session: Session) -> None:
    event = seed_event(session, areas=["estado"], change_type=2)
    drafts = by_kind(derive(session, event, FakeCima(states={"600000": STATE_REV})))

    assert set(drafts) == {"proponer_activo_n", "revisar_archivo"}
    activo = drafts["proponer_activo_n"]
    assert (activo.proposed_value, activo.rule_id) == ("N", "ADR-0019:baja-revocacion-activo:v1")
    assert activo.master_field_value_id == "fv-rec-1-ACTIVO"
    assert drafts["revisar_archivo"].proposed_value is None
    assert drafts["revisar_archivo"].master_value_literal == "activa"


def test_derive_actions_revocacion(session: Session) -> None:
    revoked = seed_event(session, areas=["estado"], suffix="b")
    drafts = by_kind(derive(session, revoked, FakeCima(states={"600000": STATE_REV})))
    assert set(drafts) == {"proponer_activo_n"}  # en lugar de revisar_estado
    assert drafts["proponer_activo_n"].proposed_value == "N"

    suspended = seed_event(session, areas=["estado"], suffix="c", epoch=2000)
    drafts = by_kind(derive(session, suspended, FakeCima(states={"600000": STATE_SUSP})))
    assert set(drafts) == {"revisar_estado"}
    assert drafts["revisar_estado"].proposed_value is None


def test_derive_actions_cima_unavailable(session: Session) -> None:
    event = seed_event(session, areas=["estado", "comerc"])
    drafts = derive(session, event, FakeCima(down=True))

    assert {draft.diagnostic_code for draft in drafts} == {"cima_no_disponible"}
    assert all(
        draft.cima_version_id is None and draft.cima_value_literal is None
        and draft.proposed_value is None
        for draft in drafts
    )
    baja = seed_event(session, areas=["estado"], change_type=2, suffix="d", epoch=2000)
    unavailable_baja = by_kind(derive(session, baja, FakeCima(down=True)))
    # Sin respuesta citable no hay propuesta ACTIVO = N.
    assert unavailable_baja["proponer_activo_n"].proposed_value is None
    assert unavailable_baja["proponer_activo_n"].diagnostic_code == "cima_no_disponible"


def test_cima_value_is_literally_in_the_cited_artifact(session: Session) -> None:
    event = seed_event(session, areas=["estado", "comerc"])
    persist_actions(session, derive(session, event, FakeCima(states={"600000": STATE_SUSP})))
    session.commit()
    for action in session.scalars(select(MaintenanceAction)):
        body = json.loads(
            reconstruct_artifact(
                session, version_id=action.cima_version_id or "", artifact_role="response",
                ordinal=1,
            )
        )
        node = body
        for part in action.cima_pointer.lstrip("/").split("/"):
            node = node[part]
        assert json.loads(action.cima_value_literal or "null") == node


def test_derive_actions_alta_estructura(session: Session) -> None:
    seed_master_header(session)
    long_name = "COMPRIMIDOS " * 30
    event = seed_event(session, areas=["estado"], change_type=1, targets=(), nregistro="9001")
    client = FakeCima(lists={"9001": listing(("777777", long_name), ("888888", "OTRO 10 mg"))})
    drafts = derive(session, event, client, default_origin=DataOrigin.REAL)

    assert {draft.national_code for draft in drafts} == {"777777", "888888"}
    first = next(draft for draft in drafts if draft.national_code == "777777")
    proposal = json.loads(first.proposal_json or "")
    assert [column["name"] for column in proposal["columns"]] == [
        "BN_IDEXTERNO", "ID_ESPECIALIDAD", "CODIGO_NACIONAL", "DESCRIPCION_PRESCRIPCION",
        "ME_DESCRIPCION", "DESCRIPCION_GESTION", "ACTIVO",
    ]
    filled = {c["name"]: c for c in proposal["columns"] if c["value"] is not None}
    assert set(filled) == {"CODIGO_NACIONAL", "DESCRIPCION_PRESCRIPCION", "DESCRIPCION_GESTION"}
    assert filled["DESCRIPCION_PRESCRIPCION"]["value"] == long_name  # sin truncar
    assert filled["DESCRIPCION_GESTION"]["provenance"]["pointer"] == "/resultados/0/nombre"
    assert filled["DESCRIPCION_GESTION"]["provenance"]["rule_id"] == (
        "ADR-0019:alta-nombre-descripcion:v1"
    )
    assert all(
        c["diagnostic"] == "sin_fuente" for c in proposal["columns"] if c["value"] is None
    )
    assert first.cima_value_literal == "777777" and first.cima_version_id


def test_alta_skips_cn_already_in_master_and_flags_missing_source(session: Session) -> None:
    seed_master_header(session)
    event = seed_event(session, areas=["estado"], change_type=1, targets=(), nregistro="9001")
    client = FakeCima(lists={"9001": listing(("600000", "YA EXISTE"), ("777777", "NUEVO"))})
    assert [d.national_code for d in derive(session, event, client)] == ["777777"]

    down = derive(session, event, FakeCima(down=True))
    assert [(d.kind, d.diagnostic_code, d.national_code) for d in down] == [
        ("proponer_alta", "cima_no_disponible", None)
    ]


def test_persist_actions_is_idempotent(session: Session) -> None:
    event = seed_event(session, areas=["estado", "comerc"])
    client = FakeCima(states={"600000": STATE_OK})
    assert persist_actions(session, derive(session, event, client)) == 2
    session.commit()
    assert persist_actions(session, derive(session, event, client)) == 0
    assert session.scalar(select(func.count()).select_from(MaintenanceAction)) == 2


def test_persist_cima_api_response_reuses_identical_content(session: Session) -> None:
    from maintenance_actions_support import response

    reply = response("https://cima.aemps.es/cima/rest/presentacion/600000", STATE_OK)
    args = {"endpoint": "presentacion", "key": "600000", "response": reply}
    first = persist_cima_api_response(session, **args)  # type: ignore[arg-type]
    again = persist_cima_api_response(session, **args)  # type: ignore[arg-type]
    assert first.created and not again.created and first.version_id == again.version_id
    assert session.scalar(select(func.count()).select_from(SourceDocumentVersion)) == 1


def test_proposed_value_requires_rule(session: Session) -> None:
    event = seed_event(session, areas=["estado"], change_type=2)
    good = by_kind(derive(session, event, FakeCima(states={"600000": STATE_REV})))
    base = good["proponer_activo_n"]
    from dataclasses import replace

    for broken in (
        replace(base, rule_id=None),
        replace(base, rule_id="OTRA:regla:v1"),
        replace(base, proposed_value="S"),
        replace(base, cima_version_id=None, cima_pointer=None, cima_value_literal=None),
        replace(base, kind="revisar_estado"),
    ):
        with pytest.raises(ActionInvariantError):
            persist_actions(session, [broken])
    with pytest.raises(ActionInvariantError):  # valor CIMA sin versión que lo cite
        persist_actions(session, [replace(good["revisar_archivo"], cima_version_id=None)])
    assert session.scalar(select(func.count()).select_from(MaintenanceAction)) == 0


def stored(session: Session, areas: list[str], states: dict[str, object],
           change_type: int = 3, suffix: str = "a") -> dict[str, MaintenanceAction]:
    event = seed_event(session, areas=areas, change_type=change_type, suffix=suffix)
    persist_actions(session, derive(session, event, FakeCima(states=states)))  # type: ignore[arg-type]
    session.commit()
    return {
        action.kind: action
        for action in session.scalars(
            select(MaintenanceAction).where(MaintenanceAction.event_id == event.id)
        )
    }


def test_action_immutable(session: Session) -> None:
    action = stored(session, ["estado"], {"600000": STATE_SUSP})["revisar_estado"]
    action.proposed_value = "N"
    with pytest.raises(ImmutableHistoryError):
        session.flush()
    session.rollback()
    session.delete(session.get(MaintenanceAction, action.id))
    with pytest.raises(ImmutableHistoryError):
        session.flush()
    session.rollback()
    decided = decide(
        session, action_id=action.id, decision="descartada", reason="Revisado",
        expected_sequence=0, reviewer=ANA,
    )
    decided.reason = "otro"
    with pytest.raises(ImmutableHistoryError):
        session.flush()


def test_decision_descartar_requiere_motivo(session: Session) -> None:
    action = stored(session, ["estado"], {"600000": STATE_SUSP})["revisar_estado"]
    with pytest.raises(ActionError, match="justificación"):
        decide(session, action_id=action.id, decision="descartada", reason="  ",
               expected_sequence=0, reviewer=ANA)
    assert session.scalar(select(func.count()).select_from(MaintenanceActionDecision)) == 0


def test_decision_concurrencia_409(session: Session) -> None:
    action = stored(session, ["estado"], {"600000": STATE_SUSP})["revisar_estado"]
    decide(session, action_id=action.id, decision="descartada", reason="Ya visto",
           expected_sequence=0, reviewer=ANA)
    with pytest.raises(ActionConflict):
        decide(session, action_id=action.id, decision="aceptada", reason="",
               expected_sequence=0, reviewer=ANA)
    with pytest.raises(ActionConflict):  # decidida: hay que reabrirla
        decide(session, action_id=action.id, decision="aceptada", reason="",
               expected_sequence=1, reviewer=ANA)
    decide(session, action_id=action.id, decision="reabierta", reason="Error mío",
           expected_sequence=1, reviewer=ANA)
    assert current_state(session, [action.id])[action.id].state == "pendiente"


def test_decision_audit_event(session: Session) -> None:
    action = stored(session, ["estado"], {"600000": STATE_SUSP})["revisar_estado"]
    decide(session, action_id=action.id, decision="aceptada", reason="Conforme",
           expected_sequence=0, reviewer=ANA)
    event = session.scalars(select(AuditEvent).where(AuditEvent.entity_id == action.id)).one()
    assert (event.entity_type, event.action, event.actor_id) == (
        "maintenance_action", "maintenance_action.decision", "ana"
    )
    assert json.loads(event.after_state)["decision"] == "aceptada"


def test_aceptar_estado_no_escribe_catalogo(session: Session) -> None:
    action = stored(session, ["estado"], {"600000": STATE_SUSP})["revisar_estado"]
    identity_before = session.get(MedicationCatalogIdentity, "ident-rec-1").version
    decide(session, action_id=action.id, decision="aceptada", reason="",
           expected_sequence=0, reviewer=ANA)
    session.expire_all()
    assert session.get(MedicationCatalogIdentity, "ident-rec-1").version == identity_before
    assert session.scalar(select(func.count()).select_from(MedicationCatalogRevision)) == 0
    assert session.scalar(select(func.count()).select_from(FieldMaintenanceRevision)) == 0


def test_aceptar_activo_n_escribe_revision(session: Session) -> None:
    actions = stored(session, ["estado"], {"600000": STATE_REV}, change_type=2)
    activo = actions["proponer_activo_n"]
    decision = decide(session, action_id=activo.id, decision="aceptada", reason="Baja confirmada",
                      expected_sequence=0, reviewer=ANA)
    revision = session.get(FieldMaintenanceRevision, decision.applied_field_revision_id)
    assert (revision.before_value, revision.after_value, revision.sequence) == ("S", "N", 1)
    assert "ADR-0019:baja-revocacion-activo:v1" in revision.reason
    assert revision.actor_id == "ana"


def test_descartar_activo_n_no_escribe(session: Session) -> None:
    activo = stored(session, ["estado"], {"600000": STATE_REV}, change_type=2)["proponer_activo_n"]
    decision = decide(session, action_id=activo.id, decision="descartada", reason="No procede",
                      expected_sequence=0, reviewer=ANA)
    assert decision.applied_field_revision_id is None
    assert session.scalar(select(func.count()).select_from(FieldMaintenanceRevision)) == 0


def test_aceptar_archivo_crea_revision(session: Session) -> None:
    archive = stored(session, ["estado"], {"600000": STATE_REV}, change_type=2)["revisar_archivo"]
    decision = decide(session, action_id=archive.id, decision="aceptada", reason="Baja AEMPS",
                      expected_sequence=0, reviewer=ANA)
    session.expire_all()
    identity = session.get(MedicationCatalogIdentity, "ident-rec-1")
    assert identity.active is False and identity.version == 2
    revision = session.get(MedicationCatalogRevision, decision.applied_revision_id)
    assert (revision.action, revision.sequence, revision.actor_id) == ("archivar", 2, "ana")
    assert "Baja AEMPS" in revision.reason


def test_unavailable_action_cannot_be_accepted(session: Session) -> None:
    event = seed_event(session, areas=["estado"])
    persist_actions(session, derive(session, event, FakeCima(down=True)))
    session.commit()
    action = session.scalars(select(MaintenanceAction)).one()
    with pytest.raises(ActionConflict, match="Pendiente de consultar CIMA"):
        decide(session, action_id=action.id, decision="aceptada", reason="",
               expected_sequence=0, reviewer=ANA)


def test_unavailable_is_superseded_by_a_later_response(session: Session) -> None:
    from sqlalchemy import select as sa_select

    from pharma_validator_api.maintenance_actions import live_actions

    event = seed_event(session, areas=["estado"])
    persist_actions(session, derive(session, event, FakeCima(down=True)))
    session.commit()
    assert session.scalars(sa_select(MaintenanceAction.id).where(live_actions())).all()
    persist_actions(session, derive(session, event, FakeCima(states={"600000": STATE_SUSP})))
    session.commit()
    live = session.scalars(sa_select(MaintenanceAction).where(live_actions())).all()
    assert [(a.kind, a.diagnostic_code) for a in live] == [
        ("revisar_estado", "sin_correspondencia")
    ]
    assert session.scalar(select(func.count()).select_from(MaintenanceAction)) == 2


def test_aceptar_alta_crea_borrador(session: Session) -> None:
    seed_master_header(session)
    event = seed_event(session, areas=["estado"], change_type=1, targets=(), suffix="e")
    persist_actions(session, derive(
        session, event, FakeCima(lists={"9001": listing(("777777", "NUEVO 10 mg"))})
    ))
    session.commit()
    alta = session.scalars(select(MaintenanceAction)).one()
    decision = decide(session, action_id=alta.id, decision="aceptada", reason="Alta real",
                      expected_sequence=0, reviewer=ANA)
    identity = session.scalars(
        select(MedicationCatalogIdentity).where(MedicationCatalogIdentity.code == "777777")
    ).one()
    assert (identity.display_name, identity.source_system) == ("NUEVO 10 mg", "cima_novedades_alta")
    assert decision.applied_revision_id
    queue = session.scalars(
        select(ReviewQueueEntry).where(
            ReviewQueueEntry.target_record_id == identity.target_record_id
        )
    ).one()
    assert (queue.review_set, queue.state) == ("corpus", "pendiente")
    with pytest.raises(ActionConflict):
        decide(session, action_id=alta.id, decision="aceptada", reason="",
               expected_sequence=1, reviewer=ANA)


def test_send_to_review_lote(session: Session) -> None:
    seed_catalog_record(session, record_id="rec-2", cn="600001")
    first = seed_event(session, areas=["estado"], suffix="a")
    second = seed_event(session, areas=["comerc"], suffix="b", epoch=2000)
    other = seed_event(
        session, areas=["estado"], suffix="c", epoch=3000, targets=(("rec-2", "600001"),)
    )
    client = FakeCima(states={"600000": STATE_SUSP, "600001": STATE_SUSP})
    for event in (first, second, other):
        persist_actions(session, derive(session, event, client))
    session.commit()
    ids = list(session.scalars(select(MaintenanceAction.id)))
    # rec-2 ya estaba en la cola: no se duplica ni se reinicia.
    from pharma_validator_api import review_queue_store

    review_queue_store.enqueue(session, "rec-2")

    result = send_to_review(session, action_ids=[*ids, "no-existe"], reviewer=ANA)
    assert result.enqueued == ["rec-1"] and result.already_queued == ["rec-2"]
    assert len(result.decided) == 3
    assert result.rejected == [{"action_id": "no-existe", "reason": "No existe."}]
    queue = session.scalars(select(ReviewQueueEntry)).all()
    assert sorted((q.target_record_id, q.review_set) for q in queue) == [
        ("rec-1", "corpus"), ("rec-2", "corpus")
    ]
    assert {current_state(session, ids)[i].state for i in ids} == {"enviada_revision"}
    again = send_to_review(session, action_ids=ids, reviewer=ANA)
    assert again.decided == [] and len(again.rejected) == 3


def test_backfill_idempotente(session: Session) -> None:
    for index in range(5):
        seed_event(session, areas=["estado", "comerc"], suffix=chr(ord("a") + index),
                   epoch=1000 + index)
    client = FakeCima(states={"600000": STATE_SUSP})
    first = backfill_actions(session, client=client, batch_size=2)  # type: ignore[arg-type]
    count = session.scalar(select(func.count()).select_from(MaintenanceAction))
    assert (first.events_processed, first.actions_created, count) == (5, 10, 10)
    # Una respuesta CIMA por CN y pasada, aunque haya cinco eventos.
    assert client.calls.count("presentacion:600000") == 1

    second = backfill_actions(session, client=client, batch_size=2)  # type: ignore[arg-type]
    assert second.events_processed == 0 and second.actions_created == 0
    assert session.scalar(select(func.count()).select_from(MaintenanceAction)) == count
    runs = session.scalars(
        select(MaintenanceRun).where(MaintenanceRun.requested_date == "backfill1")
    ).all()
    assert [(r.attempt, r.status, r.event_count) for r in runs] == [
        (1, "completed", 5), (2, "completed", 0)
    ]


def test_backfill_reanuda_tras_corte(session: Session) -> None:
    for index in range(4):
        seed_event(session, areas=["estado"], suffix=chr(ord("a") + index), epoch=1000 + index)

    class Cut(FakeCima):
        def presentation(self, *, cn: str, use_cache: bool = True):  # type: ignore[no-untyped-def]
            if len(self.calls) >= 1 and self.cut:
                raise KeyboardInterrupt
            return super().presentation(cn=cn, use_cache=use_cache)

    # Cada evento comparte CN: se capturaría una vez, así que el corte llega
    # en el segundo lote por un CN distinto.
    seed_catalog_record(session, record_id="rec-2", cn="600001")
    for index in range(2):
        seed_event(session, areas=["estado"], suffix=chr(ord("m") + index), epoch=5000 + index,
                   targets=(("rec-2", "600001"),))
    client = Cut(states={"600000": STATE_SUSP, "600001": STATE_SUSP})
    client.cut = True  # type: ignore[attr-defined]
    with pytest.raises(KeyboardInterrupt):
        backfill_actions(session, client=client, batch_size=4)  # type: ignore[arg-type]
    done = session.scalar(select(func.count()).select_from(MaintenanceAction))
    assert done == 4  # el primer lote quedó confirmado
    run = session.scalars(select(MaintenanceRun).where(
        MaintenanceRun.requested_date == "backfill1")).one()
    assert run.status == "failed"

    client.cut = False  # type: ignore[attr-defined]
    resumed = backfill_actions(session, client=client, batch_size=4)  # type: ignore[arg-type]
    assert resumed.events_processed == 2
    assert session.scalar(select(func.count()).select_from(MaintenanceAction)) == 6
    assert "presentacion:600000" not in client.calls[1:]  # no repite lo ya hecho


def test_backfill_retries_unavailable(session: Session) -> None:
    seed_event(session, areas=["estado"])
    backfill_actions(session, client=FakeCima(down=True))  # type: ignore[arg-type]
    assert session.scalar(select(func.count()).select_from(MaintenanceAction)) == 1
    retry = backfill_actions(session, client=FakeCima(states={"600000": STATE_SUSP}))  # type: ignore[arg-type]
    assert retry.events_processed == 1
    assert session.scalar(select(func.count()).select_from(MaintenanceAction)) == 2


def test_eventos_sin_target_se_guardan(session: Session) -> None:
    """D-040: la pasada diaria guarda también los avisos sin registro en el catálogo."""
    import hashlib
    from datetime import date

    from maintenance_actions_support import response

    from pharma_validator_api.cima_client import CimaResponse
    from pharma_validator_api.maintenance_job import run_one_day

    changes = [
        {"nregistro": "unlinked-1", "fecha": 5, "tipoCambio": 3, "cambio": ["prosp"]},
        {"nregistro": "unlinked-2", "fecha": 6, "tipoCambio": 3, "cambio": ["ft"]},
        {"nregistro": "9001", "fecha": 7, "tipoCambio": 3, "cambio": ["estado"]},
    ]

    class Daily(FakeCima):
        def changes(self, *, date: str, nregistros: tuple[str, ...] = ()) -> CimaResponse:
            return response("https://cima.aemps.es/cima/rest/registroCambios", changes)

        def all_presentations(self) -> tuple[dict, ...]:
            return ({"cn": "600000", "nregistro": "9001"},)

        def medication(self, **_: object) -> CimaResponse:
            raise AssertionError("un aviso sin registro en el catálogo no refresca la ficha")

    assert hashlib  # noqa: B018 - silencia importación usada solo por claridad
    run = run_one_day(session, client=Daily(states={"600000": STATE_SUSP}),  # type: ignore[arg-type]
                      day=date(2026, 10, 29))
    assert run.status == "completed" and run.event_count == 3
    nregistros = set(session.scalars(select(MaintenanceChangeEvent.nregistro)))
    assert {"unlinked-1", "unlinked-2", "9001"} <= nregistros
    # Solo el aviso enlazado genera acciones.
    actions = session.scalars(select(MaintenanceAction)).all()
    assert [(a.kind, a.target_record_id) for a in actions] == [("revisar_estado", "rec-1")]


def test_enviada_revision_solo_nace_en_send_to_review(session: Session) -> None:
    action = stored(session, ["estado"], {"600000": STATE_SUSP})["revisar_estado"]
    with pytest.raises(ActionError, match="Decisión desconocida"):
        decide(session, action_id=action.id, decision="enviada_revision", reason="",
               expected_sequence=0, reviewer=ANA)
    assert session.scalar(select(func.count()).select_from(MaintenanceActionDecision)) == 0
    assert session.scalar(select(func.count()).select_from(ReviewQueueEntry)) == 0


def test_archivar_exige_justificacion_en_el_servidor(session: Session) -> None:
    archive = stored(session, ["estado"], {"600000": STATE_REV}, change_type=2)["revisar_archivo"]
    with pytest.raises(ActionError, match="justificación"):
        decide(session, action_id=archive.id, decision="aceptada", reason="   ",
               expected_sequence=0, reviewer=ANA)
    session.expire_all()
    assert session.get(MedicationCatalogIdentity, "ident-rec-1").active is True
    assert session.scalar(select(func.count()).select_from(MaintenanceActionDecision)) == 0


def test_alta_con_propuesta_corrupta_da_error_claro(session: Session) -> None:
    from dataclasses import replace

    seed_master_header(session)
    cases = {
        "g": ('{"columns": [{"x": 1}]}', "no es válida"),
        "h": ('{"columns": [', "no es válida"),
        "i": (json.dumps({"columns": [
            {"column": 3, "name": "CODIGO_NACIONAL", "value": "1", "provenance": {}},
            {"column": 4, "name": "DESCRIPCION_PRESCRIPCION", "value": "N", "provenance": {}},
        ]}), "incompletos"),
    }
    for suffix, (broken, message) in cases.items():
        event = seed_event(session, areas=["estado"], change_type=1, targets=(), suffix=suffix)
        draft = derive(session, event, FakeCima(lists={"9001": listing(("777777", "NUEVO"))}))[0]
        persist_actions(session, [replace(draft, proposal_json=broken)])
        session.commit()
        alta = session.scalars(
            select(MaintenanceAction).where(MaintenanceAction.event_id == event.id)
        ).one()
        with pytest.raises(ActionError, match=message):
            decide(session, action_id=alta.id, decision="aceptada", reason="",
                   expected_sequence=0, reviewer=ANA)
    assert session.scalar(select(func.count()).select_from(MaintenanceActionDecision)) == 0
    assert session.scalars(select(MedicationCatalogIdentity).where(
        MedicationCatalogIdentity.source_system == "cima_novedades_alta")).all() == []


def test_fallo_de_un_evento_no_contamina_al_siguiente_del_mismo_cn(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tras el rollback del evento A no se reutiliza su versión CIMA ya borrada."""
    from datetime import date

    from maintenance_actions_support import response

    import pharma_validator_api.maintenance_actions as module
    from pharma_validator_api.cima_client import CimaResponse
    from pharma_validator_api.maintenance_job import run_one_day

    changes = [
        {"nregistro": "9001", "fecha": 5, "tipoCambio": 3, "cambio": ["estado"]},
        {"nregistro": "9001", "fecha": 6, "tipoCambio": 3, "cambio": ["comerc"]},
    ]

    class Daily(FakeCima):
        def changes(self, *, date: str, nregistros: tuple[str, ...] = ()) -> CimaResponse:
            return response("https://cima.aemps.es/cima/rest/registroCambios", changes)

        def all_presentations(self) -> tuple[dict, ...]:
            return ({"cn": "600000", "nregistro": "9001"},)

    real_persist = module.persist_actions
    calls = {"count": 0}

    def failing_first(session_: Session, drafts: object) -> int:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("fallo tras persistir la versión")
        return real_persist(session_, drafts)  # type: ignore[arg-type]

    monkeypatch.setattr(module, "persist_actions", failing_first)
    run = run_one_day(session, client=Daily(states={"600000": STATE_SUSP}),  # type: ignore[arg-type]
                      day=date(2026, 10, 29))

    assert run.status == "completed"
    assert "1 aviso sin acciones derivadas" in (run.error_detail or "")
    actions = session.scalars(select(MaintenanceAction)).all()
    assert [a.kind for a in actions] == ["revisar_comercializacion"]
    assert session.get(SourceDocumentVersion, actions[0].cima_version_id) is not None
