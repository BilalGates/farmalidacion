"""Motor de exportacion configurable (DEV-601/602/603/605).

Separacion deliberada, exigida por el punto 18 del encargo:

- `ExportProfile` describe **como** se serializa (delimitador, codificacion,
  separador decimal, orden de columnas, como se escriben los estados logicos).
- `export` aplica un perfil a unas filas y produce bytes reproducibles.

**No fija el formato del proveedor.** D-011 sigue pendiente, y D-026 advierte de
que los limites canonicos internos no equivalen a un contrato de proveedor. Por
eso el perfil es un dato, no una constante del modulo: cuando exista un ejemplo
aceptado se anadira un perfil, no se reescribira el motor.

Reglas que no se negocian:

- **Nada se trunca en silencio.** Un valor que excede su limite declarado
  produce incidencia y detiene la exportacion; recortarlo entregaria un dato
  distinto del validado sin que nadie lo supiera.
- **Los estados logicos no se aplanan a cadena vacia por defecto.** `no_consta`
  y `no_aplica` significan cosas distintas entre si y distintas de vacio; como
  se escriben es decision del perfil, no del motor.
- **Determinista**: el mismo contenido con el mismo perfil produce los mismos
  bytes y, por tanto, el mismo checksum.

Modulo puro: sin base de datos, sin reloj y sin red.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from typing import Literal

from pharma_validator_api.provenance_conflicts import LogicalState

ExportFormat = Literal["csv", "txt", "xlsx"]

#: Como se escribe cada estado logico. El perfil lo fija; el motor no supone.
StateRendering = dict[str, str]

DEFAULT_STATE_RENDERING: StateRendering = {
    "valued": "",
    "empty": "",
    "pending": "",
    "no_consta": "NO CONSTA",
    "no_aplica": "NO APLICA",
}


class ExportError(RuntimeError):
    """La exportacion no puede completarse sin alterar o perder un dato."""


@dataclass(frozen=True)
class ColumnSpec:
    """Columna de salida y su limite declarado.

    `max_length` es el limite del destino. `None` significa que no se ha
    declarado ninguno, no que sea ilimitado: sin limite declarado no se valida.
    """

    name: str
    source_field: str
    max_length: int | None = None
    required: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Una columna requiere nombre.")
        if not self.source_field:
            raise ValueError(f"La columna {self.name} requiere campo de origen.")
        if self.max_length is not None and self.max_length <= 0:
            raise ValueError(f"El limite de {self.name} debe ser positivo.")


@dataclass(frozen=True)
class ExportProfile:
    """Perfil de serializacion. Un perfil no es un contrato aceptado."""

    name: str
    fmt: ExportFormat
    columns: tuple[ColumnSpec, ...]
    delimiter: str = ";"
    encoding: str = "utf-8"
    decimal_separator: str = ","
    line_terminator: str = "\r\n"
    include_header: bool = True
    state_rendering: StateRendering = field(
        default_factory=lambda: dict(DEFAULT_STATE_RENDERING)
    )
    # Declarado explicitamente: un perfil sin contrato aceptado no debe
    # presentarse como listo para entregar al proveedor. D-011 sigue pendiente.
    provider_accepted: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Un perfil requiere nombre.")
        if not self.columns:
            raise ValueError(f"El perfil {self.name} no declara columnas.")
        names = [c.name for c in self.columns]
        if len(set(names)) != len(names):
            raise ValueError(f"El perfil {self.name} repite nombres de columna.")
        if self.fmt in ("csv", "txt") and not self.delimiter:
            raise ValueError("Un perfil delimitado requiere delimitador.")


@dataclass(frozen=True)
class ExportCell:
    """Celda a exportar: estado logico y literal, como estan almacenados."""

    logical_state: LogicalState
    literal_value: str | None = None


@dataclass(frozen=True)
class ExportIncident:
    """Motivo por el que una fila no puede exportarse tal cual."""

    row_index: int
    column: str
    kind: Literal["excede_limite", "campo_obligatorio_ausente", "estado_no_declarado"]
    detail: str


@dataclass(frozen=True)
class ExportResult:
    content: bytes
    checksum_sha256: str
    row_count: int
    profile_name: str
    incidents: tuple[ExportIncident, ...] = ()

    @property
    def is_clean(self) -> bool:
        return not self.incidents


def render_cell(profile: ExportProfile, cell: ExportCell) -> str:
    """Traduce una celda a texto segun el perfil.

    Un estado no declarado en el perfil no se aplana a vacio: seria
    indistinguible de un dato ausente. Se senala como incidencia en la
    validacion.
    """
    if cell.logical_state == "valued":
        return cell.literal_value or ""
    return profile.state_rendering.get(cell.logical_state, "")


def _decimal(value: str, separator: str) -> str:
    """Reescribe el separador decimal solo en algo que ya es un numero.

    Se comprueba antes de sustituir: aplicar la regla a texto libre corromperia
    valores que contienen puntos por otros motivos.
    """
    if separator == "." or not value:
        return value
    candidate = value.strip()
    negative = candidate.startswith("-")
    body = candidate[1:] if negative else candidate
    if not body or body.count(".") != 1:
        return value
    whole, _, fraction = body.partition(".")
    if not (whole.isdigit() and fraction.isdigit()):
        return value
    return ("-" if negative else "") + whole + separator + fraction


def validate_row(
    profile: ExportProfile, row: dict[str, ExportCell], row_index: int
) -> tuple[ExportIncident, ...]:
    """Comprueba una fila sin modificarla.

    Nada se recorta ni se rellena: la salida de esta funcion son motivos, no
    correcciones.
    """
    incidents: list[ExportIncident] = []
    for column in profile.columns:
        cell = row.get(column.source_field)
        if cell is None:
            if column.required:
                incidents.append(
                    ExportIncident(
                        row_index,
                        column.name,
                        "campo_obligatorio_ausente",
                        f"La fila no aporta {column.source_field}.",
                    )
                )
            continue
        if (
            cell.logical_state != "valued"
            and cell.logical_state not in profile.state_rendering
        ):
            incidents.append(
                ExportIncident(
                    row_index,
                    column.name,
                    "estado_no_declarado",
                    f"El perfil no declara como escribir {cell.logical_state}.",
                )
            )
            continue
        text = render_cell(profile, cell)
        if column.required and not text:
            incidents.append(
                ExportIncident(
                    row_index,
                    column.name,
                    "campo_obligatorio_ausente",
                    f"{column.name} es obligatorio y quedaria vacio.",
                )
            )
        if column.max_length is not None and len(text) > column.max_length:
            incidents.append(
                ExportIncident(
                    row_index,
                    column.name,
                    "excede_limite",
                    f"{len(text)} caracteres frente al limite {column.max_length}; "
                    "no se trunca.",
                )
            )
    return tuple(incidents)


def _rows_as_text(
    profile: ExportProfile, rows: tuple[dict[str, ExportCell], ...]
) -> list[list[str]]:
    table: list[list[str]] = []
    if profile.include_header:
        table.append([c.name for c in profile.columns])
    for row in rows:
        table.append(
            [
                _decimal(
                    render_cell(profile, row.get(c.source_field, ExportCell("empty"))),
                    profile.decimal_separator,
                )
                for c in profile.columns
            ]
        )
    return table


def export(
    profile: ExportProfile,
    rows: tuple[dict[str, ExportCell], ...],
    *,
    strict: bool = True,
) -> ExportResult:
    """Serializa las filas segun el perfil.

    En modo estricto una sola incidencia impide producir el fichero: entregar
    una exportacion con un valor truncado o un obligatorio vacio seria peor que
    no entregarla, porque parece completa.
    """
    incidents: list[ExportIncident] = []
    for index, row in enumerate(rows):
        incidents.extend(validate_row(profile, row, index))

    if incidents and strict:
        raise ExportError(
            f"{len(incidents)} incidencias impiden exportar con el perfil "
            f"{profile.name}; la primera es: {incidents[0].detail}"
        )

    table = _rows_as_text(profile, rows)
    if profile.fmt == "xlsx":
        content = _write_xlsx(table)
    else:
        buffer = io.StringIO(newline="")
        writer = csv.writer(
            buffer,
            delimiter=profile.delimiter,
            lineterminator=profile.line_terminator,
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writerows(table)
        content = buffer.getvalue().encode(profile.encoding)

    return ExportResult(
        content=content,
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        row_count=len(rows),
        profile_name=profile.name,
        incidents=tuple(incidents),
    )


def _column_name(index: int) -> str:
    name = ""
    while index >= 0:
        name = chr(ord("A") + index % 26) + name
        index = index // 26 - 1
    return name


def _write_xlsx(table: list[list[str]]) -> bytes:
    """XLSX minimo y determinista, sin dependencias externas.

    Se escribe a mano porque las bibliotecas habituales incrustan marcas de
    tiempo y metadatos que romperian la reproducibilidad byte a byte que exige
    DEV-605. Todo se escribe como texto: convertir tipos aqui inventaria
    semantica que el catalogo no declara.
    """
    # `zipfile` y `xml.sax.saxutils` se importan aqui y no arriba: arrastran
    # `ssl` de forma transitiva, y este modulo debe poder importarse en un
    # entorno sin red. No se abre ningun socket; solo se evita cargar la cadena
    # que lo definiria.
    import zipfile
    from xml.sax.saxutils import escape

    rows_xml = []
    for row_index, row in enumerate(table, start=1):
        cells = "".join(
            f'<c r="{_column_name(i)}{row_index}" t="inlineStr">'
            f'<is><t xml:space="preserve">{escape(value)}</t></is></c>'
            for i, value in enumerate(row)
        )
        rows_xml.append(f'<row r="{row_index}">{cells}</row>')
    joined = "".join(rows_xml)
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{joined}</sheetData></worksheet>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
        'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
        'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Export" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
        'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in (
            ("[Content_Types].xml", content_types),
            ("_rels/.rels", rels),
            ("xl/workbook.xml", workbook),
            ("xl/_rels/workbook.xml.rels", workbook_rels),
            ("xl/worksheets/sheet1.xml", sheet),
        ):
            # Fecha fija: el reloj no debe entrar en el contenido exportado.
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload)
    return buffer.getvalue()
