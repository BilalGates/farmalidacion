"""Manifiesto de exportacion (DEV-604/605).

Una entrega sin manifiesto no es verificable. Estas pruebas fijan que el
manifiesto describa la exportacion real y detecte cualquier alteracion.
"""

from datetime import UTC, datetime

import pytest

from pharma_validator_api.export_engine import (
    ColumnSpec,
    ExportCell,
    ExportProfile,
    export,
)
from pharma_validator_api.export_manifest import build_manifest, verify

MOMENT = datetime(2026, 9, 8, 10, 0, tzinfo=UTC)


def profile(**kwargs: object) -> ExportProfile:
    defaults: dict[str, object] = {
        "name": "perfil-tecnico",
        "fmt": "csv",
        "columns": (
            ColumnSpec("CN", "CODIGO_NACIONAL"),
            ColumnSpec("DESCRIPCION", "ME_DESCRIPCION"),
        ),
    }
    defaults.update(kwargs)
    return ExportProfile(**defaults)  # type: ignore[arg-type]


ROWS = (
    {
        "CODIGO_NACIONAL": ExportCell("valued", "707703"),
        "ME_DESCRIPCION": ExportCell("valued", "Omeprazol"),
    },
)


def test_the_manifest_describes_the_actual_export() -> None:
    active = profile()
    result = export(active, ROWS)
    manifest = build_manifest(active, result, generated_at=MOMENT)

    assert manifest.content_sha256 == result.checksum_sha256
    assert manifest.byte_size == len(result.content)
    assert manifest.row_count == 1
    assert manifest.column_names == ("CN", "DESCRIPCION")


def test_verification_accepts_the_matching_content() -> None:
    active = profile()
    result = export(active, ROWS)
    verify(build_manifest(active, result, generated_at=MOMENT), result.content)


def test_a_single_altered_byte_is_detected() -> None:
    """Un contenido que no cuadra no es una version aproximada: es otra cosa."""
    active = profile()
    result = export(active, ROWS)
    manifest = build_manifest(active, result, generated_at=MOMENT)
    tampered = result.content.replace(b"707703", b"707704")

    with pytest.raises(ValueError, match="hash"):
        verify(manifest, tampered)


def test_a_truncated_file_is_detected_by_size() -> None:
    active = profile()
    result = export(active, ROWS)
    manifest = build_manifest(active, result, generated_at=MOMENT)

    with pytest.raises(ValueError, match="bytes"):
        verify(manifest, result.content[:-3])


def test_the_manifest_is_canonical_and_reproducible() -> None:
    """Su hash debe ser estable: dos manifiestos iguales no pueden diferir."""
    active = profile()
    result = export(active, ROWS)
    first = build_manifest(active, result, generated_at=MOMENT)
    second = build_manifest(active, result, generated_at=MOMENT)

    assert first.to_json() == second.to_json()
    assert first.manifest_sha256 == second.manifest_sha256


def test_the_manifest_records_that_no_provider_contract_is_accepted() -> None:
    """D-011 pendiente: el manifiesto debe decirlo, no callarlo."""
    active = profile()
    manifest = build_manifest(active, export(active, ROWS), generated_at=MOMENT)
    assert manifest.provider_accepted is False


def test_incidents_are_counted_in_the_manifest() -> None:
    """Una entrega con incidencias no puede parecer limpia en su manifiesto."""
    strict_profile = profile(
        columns=(ColumnSpec("CN", "CODIGO_NACIONAL", max_length=3),)
    )
    result = export(strict_profile, ROWS, strict=False)
    manifest = build_manifest(strict_profile, result, generated_at=MOMENT)
    assert manifest.incident_count == 1


def test_the_profile_settings_are_recorded() -> None:
    active = profile(delimiter="|", encoding="latin-1", decimal_separator=".")
    manifest = build_manifest(active, export(active, ROWS), generated_at=MOMENT)
    assert (manifest.delimiter, manifest.encoding, manifest.decimal_separator) == (
        "|",
        "latin-1",
        ".",
    )
