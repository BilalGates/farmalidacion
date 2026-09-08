"""Puente entre los datos canónicos y el motor de exportación (DEV-601/604/605).

El motor (`export_engine`) es puro y no sabe nada de la base. Este módulo es la
capa de transformación explícita que exige el encargo: lee el modelo canónico,
lo convierte en filas de `ExportCell` y archiva la ejecución. **Ninguna
estructura del ORM se serializa directamente.**

Decisiones que sostienen la reproducibilidad:

- **El contenido lógico no depende del reloj.** La fecha vive en `ExportRun` y
  en el manifiesto, nunca dentro del fichero. Dos ejecuciones de los mismos
  datos con el mismo perfil comparten `content_hash` aunque difieran en fecha.
- **El orden es explícito.** Las filas se ordenan por identificador de registro
  y las ocurrencias por su ordinal. Sin un orden declarado, dos ejecuciones
  idénticas producirían ficheros distintos y el hash dejaría de significar nada.

Decisiones que sostienen la trazabilidad:

- **Un registro que no puede exportarse se excluye y se dice por qué.** No se
  corrige, no se recorta y no desaparece: un export con menos filas de las
  esperadas y sin explicación es indistinguible de uno correcto.
- **Fail-closed ante un estado no declarado.** Si el perfil no dice cómo se
  escribe `no_consta`, el registro se excluye en lugar de aplanarlo a vacío.
  `no_consta`, `no_aplica`, nulo y vacío significan cosas distintas (D-010) y
  colapsarlos entregaría un dato que nadie validó.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.audit_store import record_event
from pharma_validator_api.export_engine import (
    ExportCell,
    ExportError,
    ExportProfile,
    ExportResult,
    export,
    validate_row,
)
from pharma_validator_api.export_manifest import ExportManifest, build_manifest
from pharma_validator_api.models import (
    BlockInstance,
    ExportExclusion,
    ExportRun,
    FieldValue,
    TargetRecord,
)
from pharma_validator_api.provenance_conflicts import LogicalState
from pharma_validator_api.review import current_decision

#: Estados de validación cuyo valor puede entregarse.
#:
#: `pendiente` y `revision_pendiente` quedan fuera: entregar un dato que nadie
#: ha validado como si lo estuviera es exactamente lo que la exportación no
#: puede hacer. `descartado` tampoco se entrega.
EXPORTABLE_STATES = frozenset({"confirmado", "corregido", "no_consta", "no_aplica"})

#: Estado de validación -> estado lógico que entiende el motor.
STATE_TO_LOGICAL: dict[str, LogicalState] = {
    "confirmado": "valued",
    "corregido": "valued",
    "no_consta": "no_consta",
    "no_aplica": "no_aplica",
}


@dataclass(frozen=True)
class Exclusion:
    """Registro o campo que no se entrega, con su motivo."""

    target_record_id: str
    field_name: str | None
    severity: str
    rule: str
    detail: str
    observed_state: str | None = None


@dataclass(frozen=True)
class ExportOutcome:
    """Resultado completo: lo entregado, lo excluido y con qué se generó."""

    run_id: str
    result: ExportResult | None
    manifest: ExportManifest | None
    exclusions: tuple[Exclusion, ...]
    status: str

    @property
    def delivered_rows(self) -> int:
        return self.result.row_count if self.result is not None else 0

    @property
    def blocking_exclusions(self) -> tuple[Exclusion, ...]:
        return tuple(item for item in self.exclusions if item.severity == "bloqueante")


def _cell_for(
    session: Session, value: FieldValue, profile: ExportProfile
) -> tuple[ExportCell | None, Exclusion | None]:
    """Convierte un campo canónico en celda, o explica por qué no se puede."""
    decision = current_decision(session, value.id)
    if decision is None:
        return None, Exclusion(
            target_record_id="",
            field_name=value.field_name,
            severity="bloqueante",
            rule="campo_sin_validar",
            detail=(
                f"{value.field_name} no tiene ninguna decisión registrada; "
                "entregarlo daría por validado un dato que nadie revisó."
            ),
            observed_state="pendiente",
        )
    if decision.state not in EXPORTABLE_STATES:
        return None, Exclusion(
            target_record_id="",
            field_name=value.field_name,
            severity="bloqueante",
            rule="estado_no_exportable",
            detail=f"{value.field_name} está en estado {decision.state}.",
            observed_state=decision.state,
        )

    logical = STATE_TO_LOGICAL[decision.state]
    if logical != "valued" and logical not in profile.state_rendering:
        # Fail-closed: sin decisión del proveedor sobre cómo se escribe este
        # estado, aplanarlo a vacío perdería la distinción de D-010.
        return None, Exclusion(
            target_record_id="",
            field_name=value.field_name,
            severity="bloqueante",
            rule="estado_logico_no_serializable",
            detail=(
                f"El perfil {profile.name} no declara cómo escribir {logical}. "
                "Serializarlo como vacío confundiría estados que el modelo "
                "distingue (D-010/D-011)."
            ),
            observed_state=decision.state,
        )

    text = decision.final_value if logical == "valued" else None
    return ExportCell(logical_state=logical, literal_value=text), None


def collect_rows(
    session: Session,
    profile: ExportProfile,
    *,
    record_ids: tuple[str, ...] | None = None,
) -> tuple[tuple[dict[str, ExportCell], ...], tuple[Exclusion, ...]]:
    """Construye las filas exportables y la lista de exclusiones.

    Un registro con cualquier problema bloqueante queda fuera entero: entregar
    media ficha sería peor que no entregarla, porque parece completa.
    """
    query = select(TargetRecord).order_by(TargetRecord.id)
    if record_ids is not None:
        query = query.where(TargetRecord.id.in_(record_ids))

    rows: list[dict[str, ExportCell]] = []
    exclusions: list[Exclusion] = []
    needed = {column.source_field for column in profile.columns}

    for record in session.scalars(query):
        blocks = session.scalars(
            select(BlockInstance)
            .where(BlockInstance.target_record_id == record.id)
            .order_by(BlockInstance.ordinal, BlockInstance.id)
        ).all()

        row: dict[str, ExportCell] = {}
        problems: list[Exclusion] = []
        for block in blocks:
            if block.not_applicable:
                # Marcada fuera de alcance por un revisor: no es un error, pero
                # tampoco se entrega como si aplicara.
                problems.append(
                    Exclusion(
                        target_record_id=record.id,
                        field_name=None,
                        severity="no_aplicable",
                        rule="ocurrencia_no_aplicable",
                        detail=(
                            f"La ocurrencia {block.ordinal} de {block.block_type} "
                            "está marcada como no aplicable."
                        ),
                    )
                )
                continue
            for value in session.scalars(
                select(FieldValue)
                .where(FieldValue.block_instance_id == block.id)
                .order_by(FieldValue.field_name)
            ):
                if value.field_name not in needed:
                    continue
                cell, problem = _cell_for(session, value, profile)
                if problem is not None:
                    problems.append(
                        Exclusion(
                            target_record_id=record.id,
                            field_name=problem.field_name,
                            severity=problem.severity,
                            rule=problem.rule,
                            detail=problem.detail,
                            observed_state=problem.observed_state,
                        )
                    )
                    continue
                assert cell is not None
                row.setdefault(value.field_name, cell)

        # El contrato del perfil decide si la fila es entregable.
        contract = validate_row(profile, row, len(rows))
        for incident in contract:
            problems.append(
                Exclusion(
                    target_record_id=record.id,
                    field_name=incident.column,
                    severity="bloqueante",
                    rule=incident.kind,
                    detail=incident.detail,
                )
            )

        if any(item.severity == "bloqueante" for item in problems):
            exclusions.extend(problems)
            continue
        exclusions.extend(problems)
        rows.append(row)

    return tuple(rows), tuple(exclusions)


def run_export(
    session: Session,
    profile: ExportProfile,
    *,
    actor_id: str,
    actor_assurance: str = "declarada",
    record_ids: tuple[str, ...] | None = None,
    artifact_dir: Path | None = None,
    generated_at: datetime | None = None,
) -> ExportOutcome:
    """Ejecuta una exportación, la archiva y registra su rastro.

    El artefacto se escribe en disco, no en la base: un export de decenas de
    miles de fichas no cabe razonablemente en una fila. Lo que se archiva es el
    metadato suficiente para repetirlo y comprobarlo.
    """
    moment = generated_at or datetime.now(UTC)
    rows, exclusions = collect_rows(session, profile, record_ids=record_ids)

    result: ExportResult | None = None
    manifest: ExportManifest | None = None
    status = "completado"
    try:
        result = export(profile, rows, strict=True)
    except ExportError as error:
        # El motor se ha negado: la exportación no se entrega a medias.
        status = "bloqueado_por_contrato"
        exclusions = (
            *exclusions,
            Exclusion(
                target_record_id="",
                field_name=None,
                severity="bloqueante",
                rule="contrato_incumplido",
                detail=str(error),
            ),
        )

    run = ExportRun(
        profile_name=profile.name,
        profile_version=_profile_version(profile),
        export_format=profile.fmt,
        status=status,
        actor_id=actor_id,
        row_count=result.row_count if result is not None else 0,
        excluded_count=len(exclusions),
        content_hash=result.checksum_sha256 if result is not None else None,
        byte_size=len(result.content) if result is not None else None,
        artifact_path=None,
        profile_snapshot=_snapshot(profile),
        created_at=moment,
    )
    session.add(run)
    session.flush()

    if result is not None:
        manifest = build_manifest(profile, result, generated_at=moment)
        if artifact_dir is not None:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            path = artifact_dir / f"{run.id}.{profile.fmt}"
            path.write_bytes(result.content)
            run.artifact_path = str(path)

    for item in exclusions:
        session.add(
            ExportExclusion(
                export_run_id=run.id,
                target_record_id=item.target_record_id,
                field_name=item.field_name,
                severity=item.severity,
                rule=item.rule,
                detail=item.detail,
                observed_state=item.observed_state,
            )
        )

    record_event(
        session,
        entity_type="export_run",
        entity_id=run.id,
        action="exportacion",
        actor_id=actor_id,
        actor_assurance=actor_assurance,
        after_state={
            "status": status,
            "rows": run.row_count,
            "excluded": run.excluded_count,
            "hash": run.content_hash,
        },
        context={"profile": profile.name, "version": _profile_version(profile)},
        recorded_at=moment,
    )
    session.commit()

    return ExportOutcome(
        run_id=run.id,
        result=result,
        manifest=manifest,
        exclusions=exclusions,
        status=status,
    )


def _profile_version(profile: ExportProfile) -> str:
    """Versión derivada de la configuración, no declarada a mano.

    Identifica *con qué reglas* se generó un export. Derivarla del contenido
    evita que alguien cambie una columna y olvide subir el número, que es como
    dos exports incomparables acabarían declarando la misma versión.
    """
    import hashlib

    return hashlib.sha256(_snapshot(profile).encode("utf-8")).hexdigest()[:16]


def _snapshot(profile: ExportProfile) -> str:
    """Configuración usada, serializada de forma estable para poder repetirla."""
    return json.dumps(
        {
            "name": profile.name,

            "format": profile.fmt,
            "encoding": profile.encoding,
            "delimiter": profile.delimiter,
            "decimal_separator": profile.decimal_separator,
            "line_terminator": profile.line_terminator,
            "include_header": profile.include_header,
            "provider_accepted": profile.provider_accepted,
            "state_rendering": profile.state_rendering,
            "columns": [
                {
                    "name": column.name,
                    "source_field": column.source_field,
                    "max_length": column.max_length,
                    "required": column.required,
                }
                for column in profile.columns
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def exclusion_report(session: Session, run_id: str) -> list[ExportExclusion]:
    """Informe estructurado de exclusiones de una ejecución."""
    return list(
        session.scalars(
            select(ExportExclusion)
            .where(ExportExclusion.export_run_id == run_id)
            .order_by(
                ExportExclusion.severity,
                ExportExclusion.target_record_id,
                ExportExclusion.field_name,
            )
        )
    )


def archived_runs(session: Session) -> list[ExportRun]:
    """Ejecuciones archivadas, de la más reciente a la más antigua."""
    return list(
        session.scalars(select(ExportRun).order_by(ExportRun.created_at.desc()))
    )
