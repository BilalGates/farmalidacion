"""Contrato puro de identidades y relaciones del catálogo farmacéutico.

Este módulo no conoce SQLAlchemy ni fuentes concretas. Fija qué relaciones
puede representar CAT-003 antes de congelarlas en una migración y sirve al
prototipo CAT-005 para construir una navegación coherente.
"""

from dataclasses import dataclass
from typing import Literal

CatalogIdentityType = Literal[
    "commercial_product",
    "authorization",
    "presentation",
    "dcpf",
    "dcp",
    "dcsa",
    "active_ingredient",
]

CatalogRelationType = Literal[
    "product_authorization",
    "authorization_presentation",
    "presentation_dcpf",
    "dcpf_dcp",
    "dcp_dcsa",
    "dcp_active_ingredient",
]

CommercialClass = Literal["original", "generico", "biosimilar", "sin_clasificar"]

MedicationCondition = Literal[
    "huerfano",
    "estupefaciente",
    "psicotropico",
    "especial_control_medico",
    "uso_hospitalario",
]


class CatalogDomainError(ValueError):
    """El grafo propuesto contradice el contrato de dominio."""


@dataclass(frozen=True)
class CatalogIdentity:
    id: str
    identity_type: CatalogIdentityType
    display_name: str
    code: str | None = None
    target_record_id: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise CatalogDomainError("La identidad exige un identificador.")
        if not self.display_name.strip():
            raise CatalogDomainError("La identidad exige un nombre visible.")
        if self.code is not None and not self.code.strip():
            raise CatalogDomainError("Un código presente no puede estar vacío.")


@dataclass(frozen=True)
class CatalogRelation:
    relation_type: CatalogRelationType
    source_id: str
    target_id: str
    ordinal: int | None = None
    source_fragment_id: str | None = None

    def __post_init__(self) -> None:
        if self.source_id == self.target_id:
            raise CatalogDomainError("Una identidad no puede relacionarse consigo misma.")
        if self.ordinal is not None and self.ordinal < 1:
            raise CatalogDomainError("El ordinal de una relación comienza en 1.")


@dataclass(frozen=True)
class CatalogClassification:
    presentation_id: str
    commercial_class: CommercialClass
    conditions: tuple[MedicationCondition, ...]
    source_fragment_id: str | None = None

    def __post_init__(self) -> None:
        if len(set(self.conditions)) != len(self.conditions):
            raise CatalogDomainError("Una condición no puede repetirse.")


@dataclass(frozen=True)
class CatalogGraph:
    identities: tuple[CatalogIdentity, ...]
    relations: tuple[CatalogRelation, ...]
    classifications: tuple[CatalogClassification, ...] = ()


_RELATION_ENDPOINTS: dict[CatalogRelationType, tuple[CatalogIdentityType, CatalogIdentityType]] = {
    "product_authorization": ("commercial_product", "authorization"),
    "authorization_presentation": ("authorization", "presentation"),
    "presentation_dcpf": ("presentation", "dcpf"),
    "dcpf_dcp": ("dcpf", "dcp"),
    "dcp_dcsa": ("dcp", "dcsa"),
    "dcp_active_ingredient": ("dcp", "active_ingredient"),
}


def validate_catalog_graph(graph: CatalogGraph) -> CatalogGraph:
    """Comprueba identidades, extremos y composición sin inventar cardinalidad.

    Varias presentaciones pueden apuntar a un mismo DCPF, varios DCPF a un DCP y
    un DCP puede contener varias sustancias. Sólo se impiden duplicados exactos,
    extremos incompatibles, clasificaciones fuera de presentación y ciclos.
    """

    by_id: dict[str, CatalogIdentity] = {}
    for identity in graph.identities:
        if identity.id in by_id:
            raise CatalogDomainError(f"Identidad duplicada: {identity.id}.")
        by_id[identity.id] = identity

    relation_keys: set[tuple[str, str, str]] = set()
    adjacency: dict[str, list[str]] = {identity_id: [] for identity_id in by_id}
    for relation in graph.relations:
        try:
            source = by_id[relation.source_id]
            target = by_id[relation.target_id]
        except KeyError as error:
            message = f"Relación con identidad inexistente: {error.args[0]}."
            raise CatalogDomainError(message) from error
        expected = _RELATION_ENDPOINTS[relation.relation_type]
        observed = (source.identity_type, target.identity_type)
        if observed != expected:
            raise CatalogDomainError(
                f"{relation.relation_type} exige {expected[0]} → {expected[1]}, "
                f"no {observed[0]} → {observed[1]}."
            )
        key = (relation.relation_type, relation.source_id, relation.target_id)
        if key in relation_keys:
            raise CatalogDomainError("Relación duplicada.")
        relation_keys.add(key)
        adjacency[relation.source_id].append(relation.target_id)

    for classification in graph.classifications:
        classified_identity = by_id.get(classification.presentation_id)
        if classified_identity is None or classified_identity.identity_type != "presentation":
            raise CatalogDomainError("Una clasificación debe pertenecer a una presentación.")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identity_id: str) -> None:
        if identity_id in visiting:
            raise CatalogDomainError("El catálogo no puede contener ciclos.")
        if identity_id in visited:
            return
        visiting.add(identity_id)
        for child_id in adjacency[identity_id]:
            visit(child_id)
        visiting.remove(identity_id)
        visited.add(identity_id)

    for identity_id in by_id:
        visit(identity_id)
    return graph


def identity_matches(identity: CatalogIdentity, query: str) -> bool:
    """Búsqueda insensible a mayúsculas sin retirar acentos ni transformar códigos."""

    term = query.strip().casefold()
    if not term:
        return True
    return term in identity.display_name.casefold() or (
        identity.code is not None and term in identity.code.casefold()
    )
