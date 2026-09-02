"""Contrato `ExtractorLLM` e integración obligatoria del verificador (DEV-401).

La interfaz desacopla el motor de inferencia del resto del sistema: el código
habla con el modelo a través de `ExtractorLLM`, con implementaciones
intercambiables por configuración. Este módulo no abre sockets, no elige modelo
y no depende de hardware; el adaptador real es DEV-402.

La pieza que no es sustituible es `run_extraction`: toda propuesta pasa por el
verificador literal de DEV-405 antes de considerarse admitida. Una
implementación de `ExtractorLLM` no puede saltarse esa barrera, porque no es
ella quien decide qué se persiste.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol

from pharma_validator_api.evidence_verification import (
    DocumentSection,
    PrefillPolicy,
    ProposedExtraction,
    VerificationResult,
    verify_extraction,
)


class ExtractorError(RuntimeError):
    """Fallo del extractor que no debe interrumpir el lote completo."""


@dataclass(frozen=True)
class FieldRequest:
    """Campo a extraer, gobernado por el catálogo y no por código."""

    field_name: str
    description: str
    data_type: str
    policy: PrefillPolicy

    def __post_init__(self) -> None:
        if not self.field_name:
            raise ValueError("La petición de campo requiere nombre.")


@dataclass(frozen=True)
class SectionRequest:
    """Petición agrupada por sección.

    La especificación 8 exige agrupar: reunir todos los campos que dependen de
    un apartado y resolverlos en una sola llamada. Una llamada por campo
    convierte el proceso de horas en días.
    """

    document_version_id: str
    medication_name: str
    section: DocumentSection
    fields: tuple[FieldRequest, ...]

    def __post_init__(self) -> None:
        if not self.fields:
            raise ValueError("Una petición de sección requiere al menos un campo.")
        if len({item.field_name for item in self.fields}) != len(self.fields):
            raise ValueError("Los campos de una petición deben ser únicos.")
        if self.section.document_version_id != self.document_version_id:
            raise ValueError("La sección debe pertenecer a la versión solicitada.")


@dataclass(frozen=True)
class ExtractorIdentity:
    """Identidad reproducible de quien emitió una propuesta.

    Sin esto, un resultado de DEV-408 no es atribuible a un modelo concreto y la
    comparación entre tamaños deja de ser interpretable.
    """

    extractor_version: str
    model: str

    def __post_init__(self) -> None:
        if not self.extractor_version or not self.model:
            raise ValueError("La identidad del extractor requiere versión y modelo.")


class ExtractorLLM(ABC):
    """Interfaz sustituible por configuración.

    Una implementación devuelve propuestas candidatas. No persiste, no verifica
    su propia evidencia y no decide política: eso lo hace `run_extraction`.
    """

    @property
    @abstractmethod
    def identity(self) -> ExtractorIdentity: ...

    @abstractmethod
    def extract_section(self, request: SectionRequest) -> tuple[ProposedExtraction, ...]:
        """Devuelve una propuesta por campo solicitado, sin garantía de validez."""


@dataclass(frozen=True)
class FieldOutcome:
    field_name: str
    verification: VerificationResult
    proposal: ProposedExtraction | None
    identity: ExtractorIdentity

    @property
    def admitted(self) -> bool:
        return self.verification.admitted


@dataclass(frozen=True)
class SectionOutcome:
    document_version_id: str
    section: str
    identity: ExtractorIdentity
    outcomes: tuple[FieldOutcome, ...] = ()
    incidents: tuple[str, ...] = field(default_factory=tuple)

    @property
    def admitted(self) -> tuple[FieldOutcome, ...]:
        return tuple(item for item in self.outcomes if item.admitted)

    @property
    def rejected(self) -> tuple[FieldOutcome, ...]:
        return tuple(item for item in self.outcomes if not item.admitted)


class SupportsExtraction(Protocol):
    @property
    def identity(self) -> ExtractorIdentity: ...

    def extract_section(self, request: SectionRequest) -> tuple[ProposedExtraction, ...]: ...


def run_extraction(extractor: SupportsExtraction, request: SectionRequest) -> SectionOutcome:
    """Ejecuta el extractor y verifica cada propuesta antes de admitirla.

    Un fallo del extractor no bloquea la revisión manual: se registra como
    incidencia y la sección devuelve cero propuestas admitidas, según la puerta
    de salida de Fase 4.
    """
    identity = extractor.identity
    try:
        proposals = extractor.extract_section(request)
    except ExtractorError as error:
        return SectionOutcome(
            request.document_version_id,
            request.section.section,
            identity,
            incidents=(f"El extractor falló en la sección {request.section.section}: {error}",),
        )

    policies = {item.field_name: item.policy for item in request.fields}
    incidents: list[str] = []
    outcomes: list[FieldOutcome] = []
    seen: set[str] = set()

    for proposal in proposals:
        if proposal.field_name not in policies:
            incidents.append(
                f"El extractor propuso el campo no solicitado {proposal.field_name}."
            )
            continue
        if proposal.field_name in seen:
            incidents.append(
                f"El extractor propuso el campo {proposal.field_name} más de una vez."
            )
            continue
        seen.add(proposal.field_name)
        verification = verify_extraction(
            proposal, (request.section,), policies[proposal.field_name]
        )
        outcomes.append(
            FieldOutcome(
                proposal.field_name,
                verification,
                proposal if verification.admitted else None,
                identity,
            )
        )

    for missing in sorted(set(policies) - seen):
        incidents.append(f"El extractor no devolvió resultado para el campo {missing}.")

    return SectionOutcome(
        request.document_version_id,
        request.section.section,
        identity,
        tuple(sorted(outcomes, key=lambda item: item.field_name)),
        tuple(incidents),
    )


class NullExtractor(ExtractorLLM):
    """Extractor que nunca propone nada.

    Hace ejecutable el resto de la Fase 4 sin GPU y materializa la degradación
    de 8.4: con un extractor que no propone, el sistema sigue siendo útil porque
    coloca la sección correcta junto al campo correcto.
    """

    def __init__(self, extractor_version: str = "null-extractor-v1") -> None:
        self._identity = ExtractorIdentity(extractor_version, "ninguno")

    @property
    def identity(self) -> ExtractorIdentity:
        return self._identity

    def extract_section(self, request: SectionRequest) -> tuple[ProposedExtraction, ...]:
        return tuple(
            ProposedExtraction(field_name=item.field_name, state="no_encontrado")
            for item in request.fields
        )
