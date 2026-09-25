import pytest

from pharma_validator_api.catalog_domain import (
    CatalogClassification,
    CatalogDomainError,
    CatalogGraph,
    CatalogIdentity,
    CatalogRelation,
    identity_matches,
    validate_catalog_graph,
)


def identity(identifier: str, identity_type: str, name: str, code: str | None = None):
    return CatalogIdentity(identifier, identity_type, name, code)  # type: ignore[arg-type]


def valid_graph() -> CatalogGraph:
    identities = (
        identity("product", "commercial_product", "Producto combinado"),
        identity("authorization", "authorization", "Autorización", "NREG-1"),
        identity("presentation-a", "presentation", "20 comprimidos", "123456"),
        identity("presentation-b", "presentation", "40 comprimidos", "654321"),
        identity("dcpf-a", "dcpf", "10 mg + 5 mg, 20 comprimidos", "DCPF-20"),
        identity("dcpf-b", "dcpf", "10 mg + 5 mg, 40 comprimidos", "DCPF-40"),
        identity("dcp", "dcp", "10 mg + 5 mg comprimidos", "DCP-10-5"),
        identity("dcsa-a", "dcsa", "Sustancia A", "DCSA-A"),
        identity("dcsa-b", "dcsa", "Sustancia B", "DCSA-B"),
        identity("ingredient-a", "active_ingredient", "Sustancia específica A", "ING-A"),
        identity("ingredient-b", "active_ingredient", "Sustancia específica B", "ING-B"),
    )
    relations = (
        CatalogRelation("product_authorization", "product", "authorization"),
        CatalogRelation("authorization_presentation", "authorization", "presentation-a"),
        CatalogRelation("authorization_presentation", "authorization", "presentation-b"),
        CatalogRelation("presentation_dcpf", "presentation-a", "dcpf-a"),
        CatalogRelation("presentation_dcpf", "presentation-b", "dcpf-b"),
        CatalogRelation("dcpf_dcp", "dcpf-a", "dcp"),
        CatalogRelation("dcpf_dcp", "dcpf-b", "dcp"),
        CatalogRelation("dcp_dcsa", "dcp", "dcsa-a", ordinal=1),
        CatalogRelation("dcp_dcsa", "dcp", "dcsa-b", ordinal=2),
        CatalogRelation("dcp_active_ingredient", "dcp", "ingredient-a", ordinal=1),
        CatalogRelation("dcp_active_ingredient", "dcp", "ingredient-b", ordinal=2),
    )
    classifications = (
        CatalogClassification(
            "presentation-a",
            "generico",
            ("huerfano", "uso_hospitalario"),
        ),
    )
    return CatalogGraph(identities, relations, classifications)


def test_accepts_multiple_presentations_and_multiple_active_ingredients() -> None:
    assert validate_catalog_graph(valid_graph()) == valid_graph()


def test_rejects_relation_between_wrong_levels() -> None:
    graph = valid_graph()
    invalid = CatalogRelation("presentation_dcpf", "authorization", "dcpf-a")

    with pytest.raises(CatalogDomainError, match="presentation → dcpf"):
        validate_catalog_graph(CatalogGraph(graph.identities, (*graph.relations, invalid)))


def test_rejects_classification_on_a_non_presentation() -> None:
    graph = valid_graph()
    invalid = CatalogClassification("dcp", "original", ())

    with pytest.raises(CatalogDomainError, match="pertenecer a una presentación"):
        validate_catalog_graph(CatalogGraph(graph.identities, graph.relations, (invalid,)))


def test_rejects_duplicate_conditions() -> None:
    with pytest.raises(CatalogDomainError, match="no puede repetirse"):
        CatalogClassification("presentation-a", "biosimilar", ("huerfano", "huerfano"))


def test_search_matches_name_or_code_without_removing_accents() -> None:
    item = identity("ingredient", "active_ingredient", "Ácido clavulánico", "ING-42")

    assert identity_matches(item, "CLAVULÁNICO")
    assert identity_matches(item, "ing-42")
    assert not identity_matches(item, "clavulanico")

