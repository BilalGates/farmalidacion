from pharma_validator_api.models import FieldValue
from pharma_validator_api.records import _group_by_field


def test_duplicate_headers_keep_distinct_source_columns() -> None:
    first = FieldValue(
        id="field-d",
        block_instance_id="block",
        field_name="DESCRIPCION",
        source_column_index=4,
        literal_value="texto D",
        observed_type="text",
        logical_state="valued",
    )
    second = FieldValue(
        id="field-f",
        block_instance_id="block",
        field_name="DESCRIPCION",
        source_column_index=6,
        literal_value="texto F",
        observed_type="text",
        logical_state="valued",
    )
    same_source_field = FieldValue(
        id="field-d-copy",
        block_instance_id="block",
        field_name="DESCRIPCION",
        source_column_index=4,
        literal_value="evidencia D",
        observed_type="text",
        logical_state="valued",
    )

    grouped = _group_by_field(None, [first, second, same_source_field])  # type: ignore[arg-type]

    assert len(grouped) == 2
    assert grouped[("block", "DESCRIPCION", 4)] == (first, same_source_field)
    assert grouped[("block", "DESCRIPCION", 6)] == (second,)
