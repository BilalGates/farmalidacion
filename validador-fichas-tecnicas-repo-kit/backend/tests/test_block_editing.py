import pytest

from pharma_validator_api.block_editing import (
    BlockEditingError,
    BlockOccurrence,
    create_occurrence,
    delete_occurrence,
    mark_not_applicable,
    merge_occurrences,
    reorder_occurrences,
    revert_not_applicable,
)


def occurrence(
    occurrence_id: str,
    ordinal: int,
    values: tuple[tuple[str, str | None], ...] = (("VIA", "oral"),),
    origin: str | None = "master_baseline",
) -> BlockOccurrence:
    return BlockOccurrence(occurrence_id, ordinal, values, origin)


BLOCK = (
    occurrence("a", 1, (("VIA", "oral"),)),
    occurrence("b", 2, (("VIA", "intravenosa"),)),
)


def test_created_occurrence_is_appended_and_renumbered() -> None:
    edit = create_occurrence(BLOCK, occurrence("c", 99, (("VIA", "tópica"),), origin=None))
    assert [item.occurrence_id for item in edit.occurrences] == ["a", "b", "c"]
    assert [item.ordinal for item in edit.occurrences] == [1, 2, 3]


def test_created_occurrence_cannot_claim_source_provenance() -> None:
    """Un revisor no puede fabricar una fila que parezca importada."""
    with pytest.raises(BlockEditingError, match="procedencia de origen"):
        create_occurrence(BLOCK, occurrence("c", 3))


def test_duplicate_identifier_is_rejected() -> None:
    with pytest.raises(BlockEditingError, match="ya existe"):
        create_occurrence(BLOCK, occurrence("a", 3, origin=None))


def test_deleting_an_imported_occurrence_requires_a_comment() -> None:
    """Borrar una fila de origen en silencio descartaría un dato real."""
    with pytest.raises(BlockEditingError, match="exige comentario"):
        delete_occurrence(BLOCK, "a")
    edit = delete_occurrence(BLOCK, "a", comment="Duplicado confirmado con el proveedor.")
    assert [item.occurrence_id for item in edit.occurrences] == ["b"]
    assert edit.occurrences[0].ordinal == 1


def test_deleting_a_reviewer_added_occurrence_needs_no_comment() -> None:
    block = (*BLOCK, occurrence("c", 3, origin=None))
    edit = delete_occurrence(block, "c")
    assert [item.occurrence_id for item in edit.occurrences] == ["a", "b"]


def test_deleting_an_unknown_occurrence_fails() -> None:
    with pytest.raises(BlockEditingError, match="no existe"):
        delete_occurrence(BLOCK, "z", comment="x")


def test_reordering_renumbers_without_losing_occurrences() -> None:
    edit = reorder_occurrences(BLOCK, ("b", "a"))
    assert [item.occurrence_id for item in edit.occurrences] == ["b", "a"]
    assert [item.ordinal for item in edit.occurrences] == [1, 2]


def test_reordering_cannot_be_used_to_drop_an_occurrence() -> None:
    with pytest.raises(BlockEditingError, match="todas las ocurrencias"):
        reorder_occurrences(BLOCK, ("a",))


def test_reordering_rejects_a_repeated_identifier() -> None:
    with pytest.raises(BlockEditingError, match="repite"):
        reorder_occurrences(BLOCK, ("a", "a"))


def test_merging_requires_a_comment() -> None:
    with pytest.raises(BlockEditingError, match="exige comentario"):
        merge_occurrences(BLOCK, "a", "b", "  ")


def test_merging_conflicting_values_is_refused() -> None:
    """Elegir uno de dos valores clínicos sería decidir por el revisor."""
    with pytest.raises(BlockEditingError, match="valores distintos para VIA"):
        merge_occurrences(BLOCK, "a", "b", "Parecen la misma vía.")


def test_merging_complementary_occurrences_keeps_every_value() -> None:
    block = (
        occurrence("a", 1, (("VIA", "oral"), ("DOSIS", None))),
        occurrence("b", 2, (("VIA", None), ("DOSIS", "20 mg"))),
    )
    edit = merge_occurrences(block, "a", "b", "Misma vía partida en dos filas.")
    assert len(edit.occurrences) == 1
    values = dict(edit.occurrences[0].values)
    assert values == {"VIA": "oral", "DOSIS": "20 mg"}
    assert edit.occurrences[0].comment == "Misma vía partida en dos filas."


def test_merging_an_occurrence_with_itself_is_refused() -> None:
    with pytest.raises(BlockEditingError, match="consigo misma"):
        merge_occurrences(BLOCK, "a", "a", "comentario")


def test_marking_not_applicable_preserves_the_values() -> None:
    """DEV-011: se marca lógicamente sin alterar ocurrencias."""
    edit = mark_not_applicable(BLOCK, "a", "No corresponde a esta forma farmacéutica.")
    marked = edit.occurrences[0]
    assert marked.not_applicable is True
    assert marked.values == (("VIA", "oral"),)
    assert len(edit.occurrences) == 2


def test_marking_not_applicable_requires_a_comment() -> None:
    with pytest.raises(BlockEditingError, match="exige comentario"):
        mark_not_applicable(BLOCK, "a", "")


def test_not_applicable_is_reversible_with_justification() -> None:
    marked = mark_not_applicable(BLOCK, "a", "No corresponde.").occurrences
    reverted = revert_not_applicable(marked, "a", "Sí corresponde según 4.2.")
    assert reverted.occurrences[0].not_applicable is False
    assert reverted.occurrences[0].values == (("VIA", "oral"),)


def test_reverting_an_unmarked_occurrence_fails() -> None:
    with pytest.raises(BlockEditingError, match="no está marcada"):
        revert_not_applicable(BLOCK, "a", "comentario")


def test_occurrence_ordinal_starts_at_one() -> None:
    with pytest.raises(ValueError):
        BlockOccurrence("a", 0, ())


def test_occurrence_does_not_repeat_a_field() -> None:
    with pytest.raises(ValueError, match="no repite"):
        BlockOccurrence("a", 1, (("VIA", "oral"), ("VIA", "tópica")))


def test_editing_is_deterministic() -> None:
    first = reorder_occurrences(BLOCK, ("b", "a"))
    second = reorder_occurrences(BLOCK, ("b", "a"))
    assert first == second


def test_merging_is_symmetric_for_complementary_values() -> None:
    """El bug original solo miraba el ausente en un sentido."""
    block = (
        occurrence("a", 1, (("VIA", "oral"), ("DOSIS", None))),
        occurrence("b", 2, (("VIA", None), ("DOSIS", "20 mg"))),
    )
    forward = merge_occurrences(block, "a", "b", "Complementarias.")
    backward = merge_occurrences(block, "b", "a", "Complementarias.")
    assert dict(forward.occurrences[0].values) == {"VIA": "oral", "DOSIS": "20 mg"}
    assert dict(backward.occurrences[0].values) == {"VIA": "oral", "DOSIS": "20 mg"}


def test_merging_two_absent_values_keeps_the_field_absent() -> None:
    block = (
        occurrence("a", 1, (("VIA", "oral"), ("DOSIS", None))),
        occurrence("b", 2, (("DOSIS", None),)),
    )
    edit = merge_occurrences(block, "a", "b", "Complementarias.")
    assert dict(edit.occurrences[0].values) == {"VIA": "oral", "DOSIS": None}
