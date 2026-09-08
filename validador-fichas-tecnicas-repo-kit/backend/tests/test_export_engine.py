"""Motor de exportacion: perfiles, validacion y reproducibilidad (DEV-601/602/603/605).

Lo que se protege aqui es que la exportacion no pueda entregar en silencio un
dato distinto del validado: ni truncado, ni con un estado logico aplanado, ni
con un obligatorio vacio.
"""

import zipfile

import pytest

from pharma_validator_api.export_engine import (
    ColumnSpec,
    ExportCell,
    ExportError,
    ExportProfile,
    export,
    render_cell,
    validate_row,
)


def profile(**kwargs: object) -> ExportProfile:
    defaults: dict[str, object] = {
        "name": "perfil-tecnico",
        "fmt": "csv",
        "columns": (
            ColumnSpec("CN", "CODIGO_NACIONAL", max_length=6, required=True),
            ColumnSpec("DESCRIPCION", "ME_DESCRIPCION", max_length=100),
        ),
    }
    defaults.update(kwargs)
    return ExportProfile(**defaults)  # type: ignore[arg-type]


def row(cn: str = "707703", description: str = "Omeprazol") -> dict[str, ExportCell]:
    return {
        "CODIGO_NACIONAL": ExportCell("valued", cn),
        "ME_DESCRIPCION": ExportCell("valued", description),
    }


def test_a_value_over_its_limit_is_never_truncated() -> None:
    """Recortar entregaria un dato distinto del validado sin que nadie lo supiera."""
    incidents = validate_row(profile(), row(cn="1234567"), 0)
    assert len(incidents) == 1
    assert incidents[0].kind == "excede_limite"
    assert "no se trunca" in incidents[0].detail


def test_strict_export_refuses_to_produce_a_file_with_incidents() -> None:
    """Una exportacion incompleta es peor que ninguna: parece completa."""
    with pytest.raises(ExportError):
        export(profile(), (row(cn="1234567"),))


def test_non_strict_export_reports_incidents_instead_of_hiding_them() -> None:
    result = export(profile(), (row(cn="1234567"),), strict=False)
    assert not result.is_clean
    assert result.incidents[0].kind == "excede_limite"


def test_a_required_column_cannot_be_silently_empty() -> None:
    incidents = validate_row(profile(), {"ME_DESCRIPCION": ExportCell("valued", "x")}, 0)
    assert incidents[0].kind == "campo_obligatorio_ausente"


def test_logical_states_are_not_flattened_to_empty_by_default() -> None:
    """`no_consta` y `no_aplica` significan cosas distintas entre si y de vacio."""
    active = profile()
    assert render_cell(active, ExportCell("no_consta")) == "NO CONSTA"
    assert render_cell(active, ExportCell("no_aplica")) == "NO APLICA"
    assert render_cell(active, ExportCell("empty")) == ""


def test_a_profile_decides_how_states_are_written() -> None:
    """Como se escribe un estado es decision del perfil, no del motor."""
    custom = profile(state_rendering={"no_consta": "ND", "no_aplica": "NA"})
    assert render_cell(custom, ExportCell("no_consta")) == "ND"


def test_an_undeclared_state_is_an_incident_not_an_empty_cell() -> None:
    """Aplanarlo a vacio lo haria indistinguible de un dato ausente."""
    narrow = profile(state_rendering={"no_consta": "ND"})
    incidents = validate_row(
        narrow, {"CODIGO_NACIONAL": ExportCell("valued", "1"),
                 "ME_DESCRIPCION": ExportCell("no_aplica")}, 0
    )
    assert any(i.kind == "estado_no_declarado" for i in incidents)


def test_the_decimal_separator_is_configurable() -> None:
    active = profile(
        columns=(ColumnSpec("CANTIDAD", "CANTIDAD"),), decimal_separator=","
    )
    result = export(active, ({"CANTIDAD": ExportCell("valued", "10.5")},))
    assert b"10,5" in result.content


def test_the_decimal_rule_does_not_corrupt_free_text() -> None:
    """Aplicarla a texto libre romperia valores con puntos por otros motivos."""
    active = profile(columns=(ColumnSpec("TEXTO", "TEXTO"),), decimal_separator=",")
    result = export(active, ({"TEXTO": ExportCell("valued", "Vease seccion 4.2 y 5.1")},))
    assert b"4.2 y 5.1" in result.content


def test_the_delimiter_and_encoding_are_configurable() -> None:
    active = profile(delimiter="|", encoding="latin-1")
    result = export(active, (row(description="Omeprazol cápsulas"),))
    assert b"|" in result.content
    assert "cápsulas".encode("latin-1") in result.content


def test_column_order_follows_the_profile() -> None:
    reversed_profile = profile(
        columns=(
            ColumnSpec("DESCRIPCION", "ME_DESCRIPCION"),
            ColumnSpec("CN", "CODIGO_NACIONAL"),
        )
    )
    result = export(reversed_profile, (row(),))
    header = result.content.split(b"\r\n")[0]
    assert header == b"DESCRIPCION;CN"


def test_the_same_content_yields_the_same_checksum() -> None:
    """DEV-605: reproducible byte a byte, y por tanto verificable."""
    first = export(profile(), (row(), row(cn="600136", description="Otro")))
    second = export(profile(), (row(), row(cn="600136", description="Otro")))
    assert first.checksum_sha256 == second.checksum_sha256
    assert first.content == second.content


def test_a_different_profile_yields_a_different_checksum() -> None:
    assert (
        export(profile(), (row(),)).checksum_sha256
        != export(profile(delimiter="|"), (row(),)).checksum_sha256
    )


def test_xlsx_is_produced_and_is_reproducible() -> None:
    """Las bibliotecas habituales incrustan marcas de tiempo; esta no."""
    active = profile(fmt="xlsx")
    first = export(active, (row(),))
    second = export(active, (row(),))
    assert first.checksum_sha256 == second.checksum_sha256
    assert zipfile.is_zipfile(__import__("io").BytesIO(first.content))


def test_xlsx_contains_the_exported_values() -> None:
    result = export(profile(fmt="xlsx"), (row(),))
    with zipfile.ZipFile(__import__("io").BytesIO(result.content)) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml").decode()
    assert "707703" in sheet
    assert "Omeprazol" in sheet


def test_txt_uses_the_delimited_writer() -> None:
    result = export(profile(fmt="txt", delimiter="\t"), (row(),))
    assert b"\t" in result.content


def test_a_profile_without_columns_is_refused() -> None:
    with pytest.raises(ValueError):
        ExportProfile(name="vacio", fmt="csv", columns=())


def test_a_profile_cannot_repeat_column_names() -> None:
    with pytest.raises(ValueError):
        ExportProfile(
            name="repetido",
            fmt="csv",
            columns=(ColumnSpec("CN", "A"), ColumnSpec("CN", "B")),
        )


def test_profiles_are_not_provider_accepted_by_default() -> None:
    """D-011 sigue pendiente: ningun perfil puede presentarse como contrato."""
    assert profile().provider_accepted is False


def test_the_header_can_be_omitted() -> None:
    result = export(profile(include_header=False), (row(),))
    assert not result.content.startswith(b"CN;")
    assert result.row_count == 1
