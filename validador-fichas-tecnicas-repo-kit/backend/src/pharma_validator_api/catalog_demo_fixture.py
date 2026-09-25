"""Carga idempotente del caso sintético que demuestra la jerarquía CAT.

Sólo se invoca en modo DEMO. El fichero declara explícitamente ``synthetic`` y
no se usa como fuente farmacéutica ni se mezcla con una base REAL.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.catalog_domain import CatalogIdentity
from pharma_validator_api.catalog_store import create_identity
from pharma_validator_api.models import (
    MedicationCatalogClassification,
    MedicationCatalogIdentity,
    MedicationCatalogRelation,
)

_NAMESPACE = UUID("397be79e-e8fe-4cd4-a2a1-d34bc078f410")


def _id(kind: str, value: str) -> str:
    return str(uuid5(_NAMESPACE, f"{kind}:{value}"))


class IngredientFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order: int
    ingredient_code: str
    display_name: str
    dcsa_code: str
    strength: str
    strength_unit: str


class DcpFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    display_name: str
    dose_form: str
    active_ingredients: list[IngredientFixture]


class DcpfFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    display_name: str
    package_quantity: str
    package_unit: str
    dcp: DcpFixture | None = None
    dcp_ref: str | None = None


class NationalCodeFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canonical_six: str
    source_literal: str
    check_digit_status: str


class PresentationFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    national_code: NationalCodeFixture
    dcpf: DcpfFixture
    commercial_class: str
    conditions: list[str]


class AuthorizationFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    nregistro: str
    presentations: list[PresentationFixture]


class ProductFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    display_name: str
    authorizations: list[AuthorizationFixture]


class CatalogAcceptanceFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str
    synthetic: bool
    purpose: str
    commercial_products: list[ProductFixture]


def load_catalog_demo_fixture(session: Session, path: Path) -> None:
    fixture = CatalogAcceptanceFixture.model_validate_json(path.read_text(encoding="utf-8"))
    if not fixture.synthetic:
        raise ValueError("El fixture del catálogo DEMO debe declararse sintético.")
    identities: dict[str, CatalogIdentity] = {}
    relations: set[tuple[str, str, str, int | None]] = set()
    classifications: set[tuple[str, str, str]] = set()
    dcp_by_code: dict[str, tuple[str, DcpFixture]] = {}

    def add_identity(identity: CatalogIdentity) -> None:
        identities.setdefault(identity.id, identity)

    for product in fixture.commercial_products:
        add_identity(CatalogIdentity(product.id, "commercial_product", product.display_name))
        for authorization in product.authorizations:
            add_identity(
                CatalogIdentity(
                    authorization.id,
                    "authorization",
                    authorization.nregistro,
                    authorization.nregistro,
                )
            )
            relations.add(("product_authorization", product.id, authorization.id, None))
            for presentation in authorization.presentations:
                add_identity(
                    CatalogIdentity(
                        presentation.id,
                        "presentation",
                        presentation.dcpf.display_name,
                        presentation.national_code.canonical_six,
                    )
                )
                relations.add(
                    ("authorization_presentation", authorization.id, presentation.id, None)
                )
                dcpf_id = _id("dcpf", presentation.dcpf.code)
                add_identity(
                    CatalogIdentity(
                        dcpf_id,
                        "dcpf",
                        presentation.dcpf.display_name,
                        presentation.dcpf.code,
                    )
                )
                relations.add(("presentation_dcpf", presentation.id, dcpf_id, None))
                classifications.add(
                    (presentation.id, "commercial_class", presentation.commercial_class)
                )
                classifications.update(
                    (presentation.id, "condition", condition)
                    for condition in presentation.conditions
                )
                if presentation.dcpf.dcp is not None:
                    dcp = presentation.dcpf.dcp
                    dcp_id = _id("dcp", dcp.code)
                    dcp_by_code[dcp.code] = (dcp_id, dcp)
                else:
                    dcp_ref = presentation.dcpf.dcp_ref
                    if dcp_ref is None or dcp_ref not in dcp_by_code:
                        raise ValueError("El DCPF referencia un DCP aún no definido.")
                    dcp_id, dcp = dcp_by_code[dcp_ref]
                add_identity(CatalogIdentity(dcp_id, "dcp", dcp.display_name, dcp.code))
                relations.add(("dcpf_dcp", dcpf_id, dcp_id, None))
                for ingredient in dcp.active_ingredients:
                    ingredient_id = _id("ingredient", ingredient.ingredient_code)
                    dcsa_id = _id("dcsa", ingredient.dcsa_code)
                    add_identity(
                        CatalogIdentity(
                            ingredient_id,
                            "active_ingredient",
                            ingredient.display_name,
                            ingredient.ingredient_code,
                        )
                    )
                    add_identity(
                        CatalogIdentity(
                            dcsa_id,
                            "dcsa",
                            f"{ingredient.display_name} {ingredient.strength} "
                            f"{ingredient.strength_unit}",
                            ingredient.dcsa_code,
                        )
                    )
                    relations.add(
                        ("dcp_active_ingredient", dcp_id, ingredient_id, ingredient.order)
                    )
                    relations.add(("dcp_dcsa", dcp_id, dcsa_id, ingredient.order))

    existing_ids = set(session.scalars(select(MedicationCatalogIdentity.id)))
    for identity in identities.values():
        if identity.id not in existing_ids:
            source_literal = identity.code if identity.identity_type == "presentation" else None
            create_identity(
                session,
                identity,
                source_system="demo_catalog_fixture",
                source_version=fixture.schema_version,
                source_literal=source_literal,
                source_fragment_id=None,
                actor_id="sistema:fixture_catalogo_demo",
                actor_assurance="tecnica",
                reason="Carga del caso sintético de navegación del catálogo.",
            )

    existing_relations = set(
        session.execute(
            select(
                MedicationCatalogRelation.relation_type,
                MedicationCatalogRelation.source_identity_id,
                MedicationCatalogRelation.target_identity_id,
            )
        ).all()
    )
    for relation_type, source_id, target_id, ordinal in relations:
        if (relation_type, source_id, target_id) not in existing_relations:
            session.add(
                MedicationCatalogRelation(
                    id=_id("relation", f"{relation_type}:{source_id}:{target_id}"),
                    relation_type=relation_type,
                    source_identity_id=source_id,
                    target_identity_id=target_id,
                    ordinal=ordinal,
                    source_fragment_id=None,
                )
            )

    existing_classifications = set(
        session.execute(
            select(
                MedicationCatalogClassification.presentation_identity_id,
                MedicationCatalogClassification.classification_type,
                MedicationCatalogClassification.value,
            )
        ).all()
    )
    for presentation_id, classification_type, value in classifications:
        if (presentation_id, classification_type, value) not in existing_classifications:
            session.add(
                MedicationCatalogClassification(
                    id=_id("classification", f"{presentation_id}:{classification_type}:{value}"),
                    presentation_identity_id=presentation_id,
                    classification_type=classification_type,
                    value=value,
                    source_system="demo_catalog_fixture",
                    source_version=fixture.schema_version,
                    source_fragment_id=None,
                    active=True,
                )
            )
    session.commit()
