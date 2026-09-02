"""Verificación literal de evidencia previa a persistir una propuesta (DEV-405).

Implementa la regla de oro de la especificación 8.1: ninguna propuesta sin cita.
El módulo es puro y determinista. No persiste, no consulta la base de datos y no
decide política de pre-relleno; solo dictamina si una propuesta es admisible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MIN_EVIDENCE_LENGTH = 10
MAX_EVIDENCE_LENGTH = 400

ExtractionState = Literal["encontrado", "no_encontrado", "ambiguo"]
PrefillPolicy = Literal["proponer_valor", "proponer_opciones", "solo_evidencia", "oculto"]

VerificationStatus = Literal[
    "admitida",
    "rechazada_politica_oculta",
    "rechazada_sin_evidencia",
    "rechazada_seccion_desconocida",
    "rechazada_seccion_sin_texto",
    "rechazada_offsets_invalidos",
    "rechazada_texto_no_literal",
    "rechazada_longitud_evidencia",
    "rechazada_valor_sin_soporte",
    "rechazada_opciones_preseleccionadas",
]


class EvidenceVerificationError(RuntimeError):
    """Error de uso del verificador, no de contenido de la propuesta."""


@dataclass(frozen=True)
class DocumentSection:
    """Sección de una versión documental inmutable.

    `canonical_text` es la cadena contra la que se verifica la cita, tal cual se
    almacenó. No se desescapan entidades ni se normalizan espacios: hacerlo
    cambiaría el literal citado y rompería la trazabilidad con la versión.
    """

    document_version_id: str
    section: str
    canonical_text: str

    def __post_init__(self) -> None:
        if not self.document_version_id:
            raise ValueError("La sección requiere versión documental.")
        if not self.section:
            raise ValueError("La sección requiere identificador de apartado.")


@dataclass(frozen=True)
class ProposedExtraction:
    """Propuesta emitida por el extractor, todavía no persistida."""

    field_name: str
    state: ExtractionState
    proposed_value: str | None = None
    options: tuple[str, ...] = ()
    selected_option: str | None = None
    evidence_section: str | None = None
    evidence_text: str | None = None
    evidence_start: int | None = None
    evidence_end: int | None = None

    def __post_init__(self) -> None:
        if not self.field_name:
            raise ValueError("La propuesta requiere nombre de campo.")


@dataclass(frozen=True)
class VerificationResult:
    field_name: str
    status: VerificationStatus
    admitted: bool
    diagnostic: str
    verified_text: str | None = None


def _reject(
    proposal: ProposedExtraction, status: VerificationStatus, diagnostic: str
) -> VerificationResult:
    return VerificationResult(proposal.field_name, status, False, diagnostic)


def verify_extraction(
    proposal: ProposedExtraction,
    sections: tuple[DocumentSection, ...],
    policy: PrefillPolicy,
) -> VerificationResult:
    """Dictamina si una propuesta puede persistirse.

    Una propuesta rechazada nunca se corrige, se recorta ni se reescribe: se
    devuelve un diagnóstico y la propuesta se descarta como incidencia.
    """
    if len({(item.document_version_id, item.section) for item in sections}) != len(sections):
        raise EvidenceVerificationError("Las secciones deben ser únicas por versión y apartado.")

    if policy == "oculto":
        return _reject(
            proposal,
            "rechazada_politica_oculta",
            "La política del campo es oculto: no se persiste ninguna propuesta.",
        )

    if policy in ("proponer_opciones", "solo_evidencia") and proposal.selected_option is not None:
        return _reject(
            proposal,
            "rechazada_opciones_preseleccionadas",
            "Un campo protegido no puede llegar con una opción preseleccionada.",
        )

    if policy == "solo_evidencia" and proposal.proposed_value is not None:
        return _reject(
            proposal,
            "rechazada_valor_sin_soporte",
            "La política solo_evidencia no admite valor propuesto.",
        )

    if proposal.state == "no_encontrado":
        if proposal.proposed_value is not None or proposal.options:
            return _reject(
                proposal,
                "rechazada_valor_sin_soporte",
                "Un estado no_encontrado no puede aportar valor ni opciones.",
            )
        return VerificationResult(
            proposal.field_name,
            "admitida",
            True,
            "Ausencia declarada sin valor; no se persiste propuesta de valor.",
        )

    if proposal.evidence_text is None or proposal.evidence_section is None:
        return _reject(
            proposal,
            "rechazada_sin_evidencia",
            "Ninguna propuesta con valor puede persistirse sin cita.",
        )

    if proposal.evidence_start is None or proposal.evidence_end is None:
        return _reject(
            proposal,
            "rechazada_offsets_invalidos",
            "La cita requiere desplazamientos explícitos de inicio y fin.",
        )

    matching = [item for item in sections if item.section == proposal.evidence_section]
    if not matching:
        return _reject(
            proposal,
            "rechazada_seccion_desconocida",
            f"La sección citada {proposal.evidence_section} no pertenece a la versión.",
        )
    section = matching[0]

    # Las secciones de agrupación de CIMA ("4. DATOS CLÍNICOS") no traen texto:
    # su contenido vive en las subsecciones. Una cita contra ellas no es
    # verificable y se distingue de un intervalo mal calculado.
    if not section.canonical_text:
        return _reject(
            proposal,
            "rechazada_seccion_sin_texto",
            f"La sección {proposal.evidence_section} no tiene texto verificable en esta versión.",
        )

    start, end = proposal.evidence_start, proposal.evidence_end
    if start < 0 or end <= start or end > len(section.canonical_text):
        return _reject(
            proposal,
            "rechazada_offsets_invalidos",
            "Los desplazamientos citados no delimitan un intervalo dentro de la sección.",
        )

    if section.canonical_text[start:end] != proposal.evidence_text:
        return _reject(
            proposal,
            "rechazada_texto_no_literal",
            "La cita no coincide literalmente con la versión inmutable en ese intervalo.",
        )

    length = end - start
    if length < MIN_EVIDENCE_LENGTH or length > MAX_EVIDENCE_LENGTH:
        return _reject(
            proposal,
            "rechazada_longitud_evidencia",
            f"La cita mide {length} caracteres y debe medir entre "
            f"{MIN_EVIDENCE_LENGTH} y {MAX_EVIDENCE_LENGTH}.",
        )

    if proposal.state == "ambiguo" and not proposal.options:
        return _reject(
            proposal,
            "rechazada_valor_sin_soporte",
            "Un estado ambiguo debe aportar las lecturas posibles en opciones.",
        )

    if policy == "proponer_opciones" and proposal.proposed_value is not None:
        return _reject(
            proposal,
            "rechazada_valor_sin_soporte",
            "La política proponer_opciones no admite un valor único propuesto.",
        )

    return VerificationResult(
        proposal.field_name,
        "admitida",
        True,
        "Cita verificada literalmente contra la versión inmutable.",
        proposal.evidence_text,
    )
