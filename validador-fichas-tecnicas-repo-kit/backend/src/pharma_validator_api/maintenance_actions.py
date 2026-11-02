"""Acciones de mantenimiento derivadas de las novedades CIMA (ADR-0019, D-040).

Capa determinista e idempotente encima de los eventos inmutables: cada evento
con destino en el catálogo genera 0..N acciones con el valor del maestro, el
valor CIMA y un puntero a una respuesta CIMA persistida como versión inmutable.
Aquí no se decide nada y no se escribe en el catálogo: eso exige una decisión
humana (`maintenance_action_decisions`).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from pharma_validator_api.cima_client import CimaClientError, CimaResponse
from pharma_validator_api.data_origin import DataOrigin, origin_for_record
from pharma_validator_api.document_versions import (
    DocumentVersionError,
    persist_cima_api_response,
)
from pharma_validator_api.maintenance_refresh import MaintenanceClient
from pharma_validator_api.models import (
    BlockInstance,
    CatalogFieldDefinition,
    FieldMaintenanceRevision,
    FieldValue,
    ImportBatch,
    ImportedSourceSheet,
    MaintenanceAction,
    MaintenanceActionDecision,
    MaintenanceChangeEvent,
    MaintenanceChangeEventTarget,
    MaintenanceRun,
    MedicationCatalogIdentity,
)

DERIVATION_VERSION = "novedades-v1"
BACKFILL_RUN_MARK = "backfill1"  # cabe en maintenance_run.requested_date (String(10))

RULE_BAJA_ACTIVO = "ADR-0019:baja-revocacion-activo:v1"
RULE_ALTA_NOMBRE = "ADR-0019:alta-nombre-descripcion:v1"
ACCEPTED_RULES = frozenset({RULE_BAJA_ACTIVO, RULE_ALTA_NOMBRE})

KINDS = (
    "proponer_activo_n",
    "revisar_estado",
    "revisar_comercializacion",
    "revisar_archivo",
    "proponer_alta",
)
DIAG_NO_CORRESPONDENCIA = "sin_correspondencia"
DIAG_CIMA_NO_DISPONIBLE = "cima_no_disponible"
SPECIALTY_WORKBOOK = "Especialidades-CargaMaster190626.xlsx"
SPECIALTY_BLOCK = "specialty_general"
DESCRIPTION_COLUMNS = ("DESCRIPCION_PRESCRIPCION", "DESCRIPCION_GESTION")


class ActionInvariantError(ValueError):
    """Una acción rompe una regla de procedencia o de propuesta."""


@dataclass(frozen=True)
class ActionDraft:
    event_id: str
    kind: str
    area: str
    data_origin: str
    target_record_id: str | None = None
    identity_id: str | None = None
    national_code: str | None = None
    master_workbook: str | None = None
    master_sheet: str | None = None
    master_field_name: str | None = None
    master_field_value_id: str | None = None
    master_value_literal: str | None = None
    cima_version_id: str | None = None
    cima_pointer: str | None = None
    cima_value_literal: str | None = None
    proposed_value: str | None = None
    rule_id: str | None = None
    proposal_json: str | None = None
    diagnostic_code: str | None = None

    @property
    def action_id(self) -> str:
        # Una consulta sin respuesta tiene identidad propia: cuando CIMA
        # vuelva a responder nace otra acción que sustituye a esta sin tocarla.
        suffix = ":nodata" if self.diagnostic_code == DIAG_CIMA_NO_DISPONIBLE else ""
        identity = (
            f"maintenance-action:v1:{self.event_id}:{self.kind}:"
            f"{self.target_record_id or '-'}:{self.national_code or '-'}:"
            f"{self.master_field_name or '-'}{suffix}"
        )
        return str(uuid5(NAMESPACE_URL, identity))


# --- Captura de respuestas CIMA ------------------------------------------------


@dataclass(frozen=True)
class Captured:
    version_id: str
    payload: Any


class CimaCapture:
    """Pide y persiste cada respuesta CIMA una sola vez por pasada."""

    def __init__(self, session: Session, client: MaintenanceClient) -> None:
        self._session = session
        self._client = client
        self._memo: dict[tuple[str, str, int], Captured | None] = {}

    def fetch(self, endpoint: str, key: str, *, page: int = 1) -> Captured | None:
        memo_key = (endpoint, key, page)
        if memo_key in self._memo:
            return self._memo[memo_key]
        result: Captured | None = None
        try:
            response = self._request(endpoint, key, page)
            payload = json.loads(response.body)
            if isinstance(payload, dict):
                persisted = persist_cima_api_response(
                    self._session,
                    endpoint=endpoint,  # type: ignore[arg-type]
                    key=key if page == 1 else f"{key}#pagina-{page}",
                    response=response,
                )
                result = Captured(persisted.version_id, payload)
        except (CimaClientError, DocumentVersionError, ValueError):
            # JSONDecodeError y UnicodeDecodeError son ValueError.
            result = None
        self._memo[memo_key] = result
        return result

    def _request(self, endpoint: str, key: str, page: int) -> CimaResponse:
        if endpoint == "presentacion":
            return self._client.presentation(cn=key, use_cache=False)
        if endpoint == "medicamento":
            return self._client.medication(nregistro=key, use_cache=False)
        if endpoint == "presentaciones":
            return self._client.presentations(nregistro=key, pagina=page)
        raise ValueError(f"Endpoint CIMA no soportado: {endpoint}")


def pointer(*parts: str | int) -> str:
    """Puntero JSON (RFC 6901)."""
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def _literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


# --- Valores del maestro ---------------------------------------------------------


@dataclass(frozen=True)
class MasterActivo:
    field_value_id: str | None
    value: str | None


def master_activo(session: Session, target_record_id: str) -> MasterActivo:
    """`ACTIVO` de Especialidades `General` con el valor de trabajo vigente."""
    value = session.scalars(
        select(FieldValue)
        .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
        .where(
            BlockInstance.target_record_id == target_record_id,
            BlockInstance.block_type == SPECIALTY_BLOCK,
            FieldValue.field_name == "ACTIVO",
        )
        .order_by(FieldValue.id)
        .limit(1)
    ).first()
    if value is None:
        return MasterActivo(None, None)
    revision = session.scalars(
        select(FieldMaintenanceRevision)
        .where(FieldMaintenanceRevision.field_value_id == value.id)
        .order_by(FieldMaintenanceRevision.sequence.desc())
        .limit(1)
    ).first()
    return MasterActivo(value.id, revision.after_value if revision else value.literal_value)


def _identity_for(session: Session, target_record_id: str) -> MedicationCatalogIdentity | None:
    return session.scalars(
        select(MedicationCatalogIdentity)
        .where(MedicationCatalogIdentity.target_record_id == target_record_id)
        .order_by(MedicationCatalogIdentity.id)
        .limit(1)
    ).first()


def master_header(session: Session) -> list[tuple[int, str]]:
    """Columnas (índice, nombre) de la hoja General del último maestro importado."""
    payload = session.scalar(
        select(ImportedSourceSheet.header_payload)
        .join(ImportBatch, ImportBatch.id == ImportedSourceSheet.import_batch_id)
        .where(
            ImportBatch.source_locator == SPECIALTY_WORKBOOK,
            ImportBatch.status == "completed",
            ImportedSourceSheet.sheet_name == "General",
        )
        .order_by(ImportBatch.created_at.desc())
        .limit(1)
    )
    if not payload:
        return []
    cells = json.loads(payload)
    return [
        (int(cell["column"]), str(cell["literal_value"]))
        for cell in sorted(cells, key=lambda item: int(item["column"]))
        if isinstance(cell.get("literal_value"), str) and cell["literal_value"]
    ]


def _declared_length(session: Session, column: str) -> int | None:
    """Longitud declarada en el catálogo de campos, si se puede identificar sin ambigüedad.

    El catálogo abrevia algunos nombres (`DESCRIPCIONPRESCRIP`), así que se
    compara sin guiones bajos y por prefijo; sin coincidencia no se afirma nada.
    """
    wanted = column.replace("_", "")
    best: tuple[int, int] | None = None
    for name, declared in session.execute(
        select(
            CatalogFieldDefinition.field_name_literal,
            CatalogFieldDefinition.declared_type_literal,
        ).where(CatalogFieldDefinition.block_literal == "Especialidad - General")
    ):
        short = name.replace("_", "")
        match = re.fullmatch(r"\s*(?:VAR)?CHAR\((\d+)\)\s*", declared or "", re.IGNORECASE)
        if short and wanted.startswith(short) and match and (best is None or len(short) > best[0]):
            best = (len(short), int(match.group(1)))
    return best[1] if best else None


# --- Derivación -------------------------------------------------------------------


def _areas(event: MaintenanceChangeEvent) -> set[str]:
    return set(json.loads(event.areas_json))


def derive_actions(
    session: Session,
    *,
    event: MaintenanceChangeEvent,
    targets: Sequence[MaintenanceChangeEventTarget],
    client: MaintenanceClient,
    default_origin: DataOrigin = DataOrigin.REAL,
    origin_only: DataOrigin | None = None,
    capture: CimaCapture | None = None,
    include_altas: bool = True,
) -> list[ActionDraft]:
    """Acciones de un evento. Pura salvo las consultas a CIMA, que son inyectables."""
    areas = _areas(event)
    is_baja = event.change_type == 2
    capture = capture or CimaCapture(session, client)
    drafts: list[ActionDraft] = []
    linked = sorted({(item.target_record_id, item.national_code) for item in targets})
    if is_baja or areas & {"estado", "comerc"}:
        for target_id, cn in linked:
            origin = origin_for_record(session, target_id)
            if origin_only is not None and origin is not origin_only:
                continue
            drafts.extend(
                _target_actions(session, event, areas, is_baja, target_id, cn, origin, capture)
            )
    if include_altas and event.change_type == 1:
        drafts.extend(_alta_actions(session, event, linked, default_origin, capture))
    return drafts


def _cima_state(
    capture: CimaCapture, cn: str
) -> tuple[Captured | None, dict[str, Any]]:
    captured = capture.fetch("presentacion", cn)
    estado = captured.payload.get("estado") if captured else None
    return captured, estado if isinstance(estado, dict) else {}


def _target_actions(
    session: Session,
    event: MaintenanceChangeEvent,
    areas: set[str],
    is_baja: bool,
    target_id: str,
    cn: str,
    origin: DataOrigin,
    capture: CimaCapture,
) -> list[ActionDraft]:
    identity = _identity_for(session, target_id)
    activo = master_activo(session, target_id)
    captured, estado = _cima_state(capture, cn)
    version = captured.version_id if captured else None
    base: dict[str, Any] = {
        "event_id": event.id,
        "data_origin": origin.value,
        "target_record_id": target_id,
        "identity_id": identity.id if identity else None,
        "national_code": cn,
        "master_workbook": "especialidades",
        "master_sheet": "General",
        "master_field_name": "ACTIVO",
        "master_field_value_id": activo.field_value_id,
        "master_value_literal": activo.value,
        "cima_version_id": version,
    }
    unavailable = captured is None
    drafts: list[ActionDraft] = []
    revoked = estado.get("rev") is not None
    if is_baja or ("estado" in areas and revoked):
        area = "baja" if is_baja else "estado"
        drafts.append(_activo_n(base, captured, estado, unavailable, area=area))
    elif "estado" in areas:
        drafts.append(
            _review(base, "revisar_estado", "estado", "/estado", captured, estado or None)
        )
    if is_baja:
        drafts.append(
            ActionDraft(
                **{**base, "master_workbook": None, "master_sheet": None,
                   "master_field_name": None, "master_field_value_id": None,
                   "master_value_literal": (
                       "activa" if identity is None or identity.active else "archivada"
                   )},
                kind="revisar_archivo",
                area="baja",
                cima_pointer="/estado" if captured else None,
                cima_value_literal=_literal(estado) if captured and estado else None,
            )
        )
    if "comerc" in areas:
        comerc = captured.payload.get("comerc") if captured else None
        drafts.append(
            _review(
                base, "revisar_comercializacion", "comerc", "/comerc", captured,
                comerc if captured and "comerc" in captured.payload else None,
            )
        )
    return drafts


def _review(
    base: dict[str, Any], kind: str, area: str, ptr: str, captured: Captured | None, value: Any
) -> ActionDraft:
    return ActionDraft(
        **base,
        kind=kind,
        area=area,
        cima_pointer=ptr if captured else None,
        cima_value_literal=_literal(value) if captured and value is not None else None,
        diagnostic_code=DIAG_CIMA_NO_DISPONIBLE if captured is None else DIAG_NO_CORRESPONDENCIA,
    )


def _activo_n(
    base: dict[str, Any], captured: Captured | None, estado: dict[str, Any],
    unavailable: bool, *, area: str,
) -> ActionDraft:
    # Sin respuesta CIMA persistida no hay procedencia que citar: no se propone.
    return ActionDraft(
        **base,
        kind="proponer_activo_n",
        area=area,
        cima_pointer="/estado" if captured else None,
        cima_value_literal=_literal(estado) if captured and estado else None,
        proposed_value=None if unavailable else "N",
        rule_id=None if unavailable else RULE_BAJA_ACTIVO,
        diagnostic_code=DIAG_CIMA_NO_DISPONIBLE if unavailable else None,
    )


def _alta_actions(
    session: Session,
    event: MaintenanceChangeEvent,
    linked: Sequence[tuple[str, str]],
    origin: DataOrigin,
    capture: CimaCapture,
) -> list[ActionDraft]:
    base: dict[str, Any] = {
        "event_id": event.id,
        "kind": "proponer_alta",
        "area": "alta",
        "data_origin": origin.value,
        "master_workbook": "especialidades",
        "master_sheet": "General",
    }
    rows: list[tuple[Captured, int, dict[str, Any]]] = []
    page, pages = 1, 1
    while page <= pages:
        captured = capture.fetch("presentaciones", event.nregistro, page=page)
        if captured is None:
            if page == 1:
                return [ActionDraft(**base, diagnostic_code=DIAG_CIMA_NO_DISPONIBLE)]
            break
        size, total = captured.payload.get("tamanioPagina"), captured.payload.get("totalFilas")
        if isinstance(size, int) and isinstance(total, int) and size > 0:
            pages = (total + size - 1) // size
        results = captured.payload.get("resultados")
        for index, row in enumerate(results if isinstance(results, list) else []):
            if isinstance(row, dict):
                rows.append((captured, index, row))
        page += 1
    known = {cn for _, cn in linked}
    candidates = [
        (captured, index, row) for captured, index, row in rows
        if isinstance(row.get("cn"), str) and row["cn"] and row["cn"] not in known
    ]
    in_master = set(
        session.scalars(
            select(FieldValue.literal_value).where(
                FieldValue.field_name == "CODIGO_NACIONAL",
                FieldValue.literal_value.in_([row["cn"] for _, _, row in candidates]),
            )
        )
    ) if candidates else set()
    header = master_header(session)
    drafts = []
    for captured, index, row in candidates:
        if row["cn"] in in_master:
            continue
        name = row.get("nombre") if isinstance(row.get("nombre"), str) and row["nombre"] else None
        proposal = _proposal(session, header, captured.version_id, index, row["cn"], name)
        drafts.append(
            ActionDraft(
                **base,
                national_code=row["cn"],
                cima_version_id=captured.version_id,
                cima_pointer=pointer("resultados", index, "cn"),
                cima_value_literal=row["cn"],
                rule_id=RULE_ALTA_NOMBRE,
                proposal_json=json.dumps(proposal, ensure_ascii=False),
                diagnostic_code=None if header else "sin_cabecera_maestro",
            )
        )
    return drafts


def _proposal(
    session: Session, header: list[tuple[int, str]], version_id: str, index: int,
    cn: str, name: str | None,
) -> dict[str, Any]:
    columns: list[dict[str, Any]] = []
    for column, title in header:
        value: str | None = None
        provenance: dict[str, Any] | None = None
        if title == "CODIGO_NACIONAL":
            value = cn
            provenance = {
                "cima_version_id": version_id,
                "pointer": pointer("resultados", index, "cn"),
            }
        elif title in DESCRIPTION_COLUMNS and name is not None:
            value = name
            provenance = {
                "cima_version_id": version_id,
                "pointer": pointer("resultados", index, "nombre"),
                "rule_id": RULE_ALTA_NOMBRE,
            }
        diagnostic = None if value is not None else "sin_fuente"
        if value is not None:
            limit = _declared_length(session, title)
            if limit is not None and len(value) > limit:
                diagnostic = "excede_longitud"
        columns.append(
            {"column": column, "name": title, "value": value,
             "provenance": provenance, "diagnostic": diagnostic}
        )
    return {"workbook": "especialidades", "sheet": "General", "columns": columns}


# --- Persistencia ------------------------------------------------------------------


def _check(draft: ActionDraft) -> None:
    if draft.kind not in KINDS:
        raise ActionInvariantError(f"Tipo de acción desconocido: {draft.kind}")
    if draft.data_origin not in {origin.value for origin in DataOrigin}:
        raise ActionInvariantError("Toda acción exige un origen REAL o DEMO.")
    if draft.cima_value_literal is not None and draft.cima_version_id is None:
        raise ActionInvariantError("Un valor CIMA exige la respuesta inmutable que lo respalda.")
    if draft.proposed_value is not None:
        if draft.rule_id not in ACCEPTED_RULES:
            raise ActionInvariantError("Un valor propuesto exige una regla aceptada (ADR-0019).")
        if draft.cima_version_id is None:
            raise ActionInvariantError("Un valor propuesto exige la respuesta CIMA que lo cita.")
        if draft.kind != "proponer_activo_n" or draft.proposed_value != "N":
            raise ActionInvariantError("La regla solo propone ACTIVO = N para bajas.")
    elif draft.kind == "proponer_activo_n" and draft.diagnostic_code != DIAG_CIMA_NO_DISPONIBLE:
        raise ActionInvariantError("proponer_activo_n sin valor exige diagnóstico de CIMA.")


def persist_actions(session: Session, drafts: Iterable[ActionDraft]) -> int:
    """Inserta solo las acciones nuevas; no hace commit."""
    pending = {draft.action_id: draft for draft in drafts}
    for draft in pending.values():
        _check(draft)
    if not pending:
        return 0
    ids = list(pending)
    existing: set[str] = set()
    for start in range(0, len(ids), 500):
        existing.update(
            session.scalars(
                select(MaintenanceAction.id).where(MaintenanceAction.id.in_(ids[start:start + 500]))
            )
        )
    now = datetime.now(UTC)
    created = 0
    for action_id, draft in pending.items():
        if action_id in existing:
            continue
        values = {name: getattr(draft, name) for name in draft.__dataclass_fields__}
        session.add(
            MaintenanceAction(
                id=action_id, derivation_version=DERIVATION_VERSION, created_at=now, **values
            )
        )
        created += 1
    session.flush()
    return created


def derive_for_events(
    session: Session,
    *,
    events: Iterable[MaintenanceChangeEvent],
    client: MaintenanceClient,
    default_origin: DataOrigin = DataOrigin.REAL,
    origin_only: DataOrigin | None = None,
    capture: CimaCapture | None = None,
    include_altas: bool = True,
) -> int:
    """Deriva y persiste las acciones de varios eventos; no hace commit."""
    capture = capture or CimaCapture(session, client)
    created = 0
    for event in events:
        targets = session.scalars(
            select(MaintenanceChangeEventTarget).where(
                MaintenanceChangeEventTarget.event_id == event.id
            )
        ).all()
        created += persist_actions(
            session,
            derive_actions(
                session, event=event, targets=targets, client=client,
                default_origin=default_origin, origin_only=origin_only, capture=capture,
                include_altas=include_altas,
            ),
        )
    return created


# --- Estado vigente --------------------------------------------------------------


@dataclass(frozen=True)
class ActionState:
    state: str  # pendiente | aceptada | descartada | enviada_revision
    sequence: int
    decision: MaintenanceActionDecision | None = None


def current_state(session: Session, action_ids: Sequence[str]) -> dict[str, ActionState]:
    states = {action_id: ActionState("pendiente", 0) for action_id in action_ids}
    for start in range(0, len(action_ids), 500):
        chunk = list(action_ids[start:start + 500])
        latest = (
            select(
                MaintenanceActionDecision.action_id,
                func.max(MaintenanceActionDecision.sequence).label("sequence"),
            )
            .where(MaintenanceActionDecision.action_id.in_(chunk))
            .group_by(MaintenanceActionDecision.action_id)
            .subquery()
        )
        for decision in session.scalars(
            select(MaintenanceActionDecision).join(
                latest,
                and_(
                    MaintenanceActionDecision.action_id == latest.c.action_id,
                    MaintenanceActionDecision.sequence == latest.c.sequence,
                ),
            )
        ):
            state = "pendiente" if decision.decision == "reabierta" else decision.decision
            states[decision.action_id] = ActionState(state, decision.sequence, decision)
    return states


def live_actions() -> Any:
    """Condición SQL: acciones no sustituidas por una consulta CIMA posterior."""
    sibling = aliased(MaintenanceAction)
    superseded = exists().where(
        sibling.event_id == MaintenanceAction.event_id,
        sibling.area == MaintenanceAction.area,
        sibling.target_record_id.is_not_distinct_from(MaintenanceAction.target_record_id),
        or_(
            MaintenanceAction.national_code.is_(None),
            sibling.national_code == MaintenanceAction.national_code,
        ),
        sibling.cima_version_id.is_not(None),
    )
    return or_(MaintenanceAction.diagnostic_code != DIAG_CIMA_NO_DISPONIBLE,
               MaintenanceAction.diagnostic_code.is_(None),
               ~superseded)


def pending_condition() -> Any:
    """Condición SQL: sin decisión o con la última en `reabierta`."""
    latest = (
        select(
            MaintenanceActionDecision.action_id.label("action_id"),
            func.max(MaintenanceActionDecision.sequence).label("sequence"),
        )
        .group_by(MaintenanceActionDecision.action_id)
        .subquery()
    )
    decided = (
        select(MaintenanceActionDecision.action_id)
        .join(
            latest,
            and_(
                MaintenanceActionDecision.action_id == latest.c.action_id,
                MaintenanceActionDecision.sequence == latest.c.sequence,
            ),
        )
        .where(MaintenanceActionDecision.decision != "reabierta")
    )
    return MaintenanceAction.id.not_in(decided)


# --- Backfill ----------------------------------------------------------------------


@dataclass
class BackfillResult:
    events_seen: int = 0
    events_processed: int = 0
    actions_created: int = 0
    run_id: str | None = None
    stopped_early: bool = False


def backfill_actions(
    session: Session,
    *,
    client: MaintenanceClient,
    batch_size: int = 200,
    limit: int | None = None,
    origin: DataOrigin = DataOrigin.REAL,
    on_progress: Callable[[int], None] | None = None,
    retry_unavailable: bool = True,
) -> BackfillResult:
    """Deriva acciones de los eventos con destino, por lotes y reanudable.

    Los ids son deterministas: relanzar no duplica. Un evento que ya tiene
    acciones no vuelve a consultar CIMA, así que tras un corte se continúa donde
    se quedó. Con `retry_unavailable` se reintentan los que solo tienen
    consultas sin respuesta. Toma el valor CIMA *actual*, no el del día del aviso.
    """
    result = BackfillResult()
    attempt = (
        session.scalar(
            select(func.max(MaintenanceRun.attempt)).where(
                MaintenanceRun.requested_date == BACKFILL_RUN_MARK
            )
        )
        or 0
    ) + 1
    run = MaintenanceRun(
        requested_date=BACKFILL_RUN_MARK, attempt=attempt, status="running", event_count=0,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    session.commit()
    result.run_id = run.id
    capture = CimaCapture(session, client)
    done = set(session.scalars(select(MaintenanceAction.event_id).distinct()))
    unresolved: set[str] = set()
    if retry_unavailable:
        unresolved = set(
            session.scalars(
                select(MaintenanceAction.event_id)
                .where(MaintenanceAction.diagnostic_code == DIAG_CIMA_NO_DISPONIBLE)
                .where(live_actions())
                .distinct()
            )
        )
    last: tuple[int, str] | None = None
    try:
        while True:
            query = (
                select(MaintenanceChangeEvent)
                .where(
                    exists().where(
                        MaintenanceChangeEventTarget.event_id == MaintenanceChangeEvent.id
                    )
                )
                .order_by(MaintenanceChangeEvent.occurred_at_epoch, MaintenanceChangeEvent.id)
                .limit(batch_size)
            )
            if last is not None:
                query = query.where(
                    or_(
                        MaintenanceChangeEvent.occurred_at_epoch > last[0],
                        and_(
                            MaintenanceChangeEvent.occurred_at_epoch == last[0],
                            MaintenanceChangeEvent.id > last[1],
                        ),
                    )
                )
            batch = session.scalars(query).all()
            if not batch:
                break
            todo = []
            for event in batch:
                result.events_seen += 1
                if event.id not in done or event.id in unresolved:
                    todo.append(event)
            if limit is not None:
                todo = todo[: max(limit - result.events_processed, 0)]
            result.actions_created += derive_for_events(
                session, events=todo, client=client, origin_only=origin, capture=capture,
                include_altas=False,
            )
            result.events_processed += len(todo)
            run.event_count = result.events_processed
            session.commit()
            if on_progress is not None:
                on_progress(result.events_processed)
            last = (batch[-1].occurred_at_epoch, batch[-1].id)
            if limit is not None and result.events_processed >= limit:
                result.stopped_early = True
                break
        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        session.commit()
    except BaseException as error:
        session.rollback()
        stored = session.get(MaintenanceRun, run.id)
        if stored is not None:
            stored.status = "failed"
            stored.error_detail = f"{type(error).__name__}: {error}"[:2000]
            stored.finished_at = datetime.now(UTC)
            session.commit()
        raise
    return result
