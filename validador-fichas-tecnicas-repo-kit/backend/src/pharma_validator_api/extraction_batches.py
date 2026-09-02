"""Planificación reanudable de lotes de extracción (DEV-406).

La puerta de salida de Fase 4 exige que el corpus se procese de forma
reanudable, con control de versiones de prompt y modelo y observabilidad. El
volumen del piloto son 500 documentos por ~15 llamadas: unas 7.500 peticiones,
una noche de proceso. Reiniciar desde cero por una interrupción es inaceptable.

El módulo es puro: decide qué unidades faltan y cuáles se conservan, sin abrir
sockets ni persistir. Quien ejecute el plan aporta el estado ya completado.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from pharma_validator_api.extractor import ExtractorIdentity, SectionRequest
from pharma_validator_api.section_grouping import section_sort_key

PLANNER_VERSION = "extraction-batch-v1"

UnitStatus = Literal["pendiente", "completada", "incidencia"]


class ExtractionBatchError(RuntimeError):
    """Uso incoherente del planificador, no fallo de una unidad."""


@dataclass(frozen=True)
class ExtractionConfiguration:
    """Todo lo que cambia el resultado de una extracción.

    Prompt, esquema, modelo y versión del extractor forman parte de la
    identidad: un cambio en cualquiera de ellos produce propuestas distintas y
    no puede reutilizar el trabajo anterior como si fuera equivalente.
    """

    identity: ExtractorIdentity
    prompt_version: str
    schema_version: str

    def __post_init__(self) -> None:
        if not self.prompt_version or not self.schema_version:
            raise ValueError("La configuración requiere versión de prompt y de esquema.")

    def fingerprint(self) -> str:
        payload = json.dumps(
            {
                "planner": PLANNER_VERSION,
                "extractor_version": self.identity.extractor_version,
                "model": self.identity.model,
                "prompt_version": self.prompt_version,
                "schema_version": self.schema_version,
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WorkUnit:
    """Unidad reanudable: una llamada por versión documental y apartado."""

    document_version_id: str
    section: str
    field_names: tuple[str, ...]

    @property
    def key(self) -> str:
        payload = json.dumps(
            {
                "document_version_id": self.document_version_id,
                "section": self.section,
                "fields": sorted(self.field_names),
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CompletedUnit:
    """Unidad ya resuelta en una ejecución anterior."""

    key: str
    configuration_fingerprint: str
    status: UnitStatus

    def __post_init__(self) -> None:
        if self.status == "pendiente":
            raise ValueError("Una unidad completada no puede estar pendiente.")


@dataclass(frozen=True)
class BatchPlan:
    configuration_fingerprint: str
    pending: tuple[SectionRequest, ...]
    reused: tuple[str, ...]
    retried: tuple[str, ...]
    superseded: tuple[str, ...]

    @property
    def total_units(self) -> int:
        return len(self.pending) + len(self.reused)


def plan_batch(
    requests: tuple[SectionRequest, ...],
    configuration: ExtractionConfiguration,
    completed: tuple[CompletedUnit, ...] = (),
    retry_incidents: bool = True,
) -> BatchPlan:
    """Decide qué unidades quedan pendientes.

    Una unidad completada solo se reutiliza si se resolvió con la misma
    configuración. Un cambio de modelo, prompt o esquema no invalida ni borra el
    trabajo anterior: lo marca como superado y vuelve a planificar la unidad,
    de modo que dos configuraciones puedan compararse en DEV-408.
    """
    fingerprint = configuration.fingerprint()

    units = {
        WorkUnit(
            item.document_version_id,
            item.section.section,
            tuple(field.field_name for field in item.fields),
        ).key: item
        for item in requests
    }
    if len(units) != len(requests):
        raise ExtractionBatchError(
            "Dos peticiones producen la misma unidad de trabajo; revise la agrupación."
        )

    seen: set[str] = set()
    reused: list[str] = []
    retried: list[str] = []
    superseded: list[str] = []

    for unit in completed:
        if unit.key in seen:
            raise ExtractionBatchError(f"La unidad {unit.key} aparece repetida en el estado.")
        seen.add(unit.key)
        if unit.key not in units:
            # Trabajo de otro lote o de una agrupación anterior: no se toca.
            continue
        if unit.configuration_fingerprint != fingerprint:
            superseded.append(unit.key)
            continue
        if unit.status == "incidencia" and retry_incidents:
            retried.append(unit.key)
            continue
        reused.append(unit.key)

    resolved = set(reused)
    # El orden de proceso sigue documento y apartado, no el hash de la clave:
    # un lote de 7.500 peticiones debe ser legible mientras avanza.
    pending = tuple(
        sorted(
            (request for key, request in units.items() if key not in resolved),
            key=lambda item: (
                item.document_version_id,
                section_sort_key(item.section.section),
            ),
        )
    )
    return BatchPlan(
        fingerprint,
        pending,
        tuple(sorted(reused)),
        tuple(sorted(retried)),
        tuple(sorted(superseded)),
    )
