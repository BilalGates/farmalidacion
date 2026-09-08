"""Madurez de cada capacidad: implementada no es lo mismo que validada.

Este módulo existe para que una afirmación como «la revisión está lista» no
pueda hacerse de forma ambigua. Cuatro niveles, y el salto a
`clinicamente_validada` **no lo puede dar el código**: exige conjunto oro
anotado por farmacéuticos, métricas publicadas y umbrales aceptados.

Que una capacidad esté `tecnicamente_verificada` significa que sus pruebas
pasan, no que su resultado sea clínicamente correcto.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MaturityLevel = Literal[
    "implementada",
    "tecnicamente_verificada",
    "clinicamente_validada",
    "lista_para_produccion",
]

_ORDER: tuple[MaturityLevel, ...] = (
    "implementada",
    "tecnicamente_verificada",
    "clinicamente_validada",
    "lista_para_produccion",
)


class MaturityError(RuntimeError):
    """Se ha afirmado una madurez que la evidencia disponible no sostiene."""


@dataclass(frozen=True)
class Capability:
    name: str
    level: MaturityLevel
    # Bloqueos que impiden subir de nivel. Vacío no significa «sin bloqueos»
    # para los niveles clínicos: significa que nadie los ha declarado.
    clinical_blockers: tuple[str, ...] = ()
    note: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Una capacidad requiere nombre.")
        if self.level in ("clinicamente_validada", "lista_para_produccion") and (
            self.clinical_blockers
        ):
            raise MaturityError(
                f"«{self.name}» no puede declararse {self.level} con bloqueos "
                f"clínicos abiertos: {', '.join(self.clinical_blockers)}."
            )

    @property
    def is_clinically_validated(self) -> bool:
        return self.level in ("clinicamente_validada", "lista_para_produccion")


def rank(level: MaturityLevel) -> int:
    return _ORDER.index(level)


# Estado declarado del proyecto. Se mantiene junto al código y no en un
# documento suelto, para que una suite pueda comprobarlo.
CAPABILITIES: tuple[Capability, ...] = (
    Capability("ingesta_maestros", "tecnicamente_verificada"),
    Capability("listado_y_busqueda_real", "tecnicamente_verificada"),
    Capability("procedencia_y_versiones", "tecnicamente_verificada"),
    Capability("cola_de_revision", "tecnicamente_verificada"),
    Capability("decisiones_y_auditoria", "tecnicamente_verificada"),
    Capability("medicion_de_tiempos", "tecnicamente_verificada"),
    Capability(
        "doble_validacion",
        "tecnicamente_verificada",
        clinical_blockers=("GOLD-002",),
        note="Comparacion y conciliacion probadas con revisores ficticios; "
        "la campana real exige dos farmaceuticos.",
    ),
    Capability(
        "extractor_llm",
        "implementada",
        clinical_blockers=("D-014",),
        note="Transporte y adaptador probados sin GPU; falta runtime aceptado.",
    ),
    Capability(
        "prefill_de_propuestas",
        "implementada",
        clinical_blockers=("GOLD-002", "D-015"),
        note="Sin umbrales derivados de métricas reales no debe activarse.",
    ),
    Capability(
        "evaluacion_contra_oro",
        "implementada",
        clinical_blockers=("GOLD-002", "GOLD-004"),
        note="Motor probado con entradas sintéticas; no hay anotación real.",
    ),
    Capability(
        "motor_de_exportacion",
        "tecnicamente_verificada",
        clinical_blockers=("D-011",),
        note="Perfiles configurables, sin truncado silencioso y reproducible; "
        "el contrato exacto del proveedor sigue sin aceptar.",
    ),
    Capability(
        "vinculo_maestro_cima",
        "implementada",
        clinical_blockers=("D-027",),
        note="Auditoría exacta reproducible; no se persiste ningún vínculo.",
    ),
)


def clinical_blockers() -> tuple[str, ...]:
    """Bloqueos clínicos abiertos, sin repetir, en orden estable."""
    seen: list[str] = []
    for capability in CAPABILITIES:
        for blocker in capability.clinical_blockers:
            if blocker not in seen:
                seen.append(blocker)
    return tuple(sorted(seen))


def assert_no_capability_claims_clinical_validation() -> None:
    """Ninguna capacidad puede declararse validada mientras no exista oro real."""
    claimed = [c.name for c in CAPABILITIES if c.is_clinically_validated]
    if claimed:
        raise MaturityError(
            "Ninguna capacidad puede declararse clínicamente validada sin conjunto "
            f"oro anotado: {', '.join(claimed)}."
        )
