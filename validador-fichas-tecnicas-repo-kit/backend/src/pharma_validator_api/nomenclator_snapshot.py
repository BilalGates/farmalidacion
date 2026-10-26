"""Instantánea acotada de dbo.nomenclatur exportada sin datos de pacientes.

El TSV de SSMS no trae cabecera. Los índices provienen del inventario de columnas
de la misma exportación y se comprueban por cardinalidad antes de servirlo.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class NomenclatorField:
    name: str
    label: str
    column: int
    master_field: str | None = None
    level: str = "presentacion"


FIELDS = (
    NomenclatorField("nro_definitivo", "Número de registro", 2),
    NomenclatorField("cod_atc", "Código ATC", 48, "MED_ATC", "medicamento"),
    NomenclatorField("cod_dcp", "Código DCP", 6, "MED_DCP", "medicamento"),
    NomenclatorField("cod_dcsa", "Código DCSA", 5),
    NomenclatorField("cod_dcpf", "Código DCPF", 7),
    NomenclatorField("formafarmaceutica", "Forma farmacéutica", 59),
    NomenclatorField("principioactivo", "Principio activo declarado", 65),
    NomenclatorField("estado", "Estado en Nomenclátor", 63),
    NomenclatorField("sw_uso_hospitalario", "Uso hospitalario", 26, "SW_USO_HOSPITALARIO"),
    NomenclatorField("sw_generico", "Genérico", 23),
    NomenclatorField("biosimilar", "Biosimilar", 43),
    NomenclatorField("url_fictec", "Ficha técnica", 20),
)
FIELD_BY_NAME = {field.name: field for field in FIELDS}


@dataclass(frozen=True)
class NomenclatorSnapshot:
    sha256: str
    row_count: int
    latest_source_date: str | None
    rows: dict[str, NomenclatorRow]


@dataclass(frozen=True)
class NomenclatorRow:
    line_number: int
    columns: tuple[str, ...]


def _value(row: tuple[str, ...], index: int) -> str | None:
    value = row[index].strip()
    return value if value and value.upper() != "NULL" else None


def source_value(row: tuple[str, ...], field: NomenclatorField) -> str | None:
    return _value(row, field.column)


@lru_cache(maxsize=4)
def _load_snapshot(path: str, size: int, modified_ns: int) -> NomenclatorSnapshot:
    del size, modified_ns  # Sólo identifican la versión de caché.
    digest = hashlib.sha256()
    rows: dict[str, NomenclatorRow] = {}
    latest_date: str | None = None
    with Path(path).open("rb") as stream:
        for number, raw in enumerate(stream, start=1):
            digest.update(raw)
            try:
                columns = tuple(raw.decode("utf-8-sig").rstrip("\r\n").split("\t"))
            except UnicodeDecodeError as error:
                raise ValueError(f"Fila {number}: codificación UTF-8 inválida.") from error
            if len(columns) != 73:
                raise ValueError(f"Fila {number}: se esperaban 73 columnas; hay {len(columns)}.")
            cn = columns[1].strip()
            if len(cn) != 6 or not cn.isascii() or not cn.isdigit():
                raise ValueError(f"Fila {number}: código nacional no válido.")
            if cn in rows:
                raise ValueError(f"Fila {number}: código nacional duplicado {cn}.")
            rows[cn] = NomenclatorRow(number, columns)
            date = _value(columns, 62)
            if date and (latest_date is None or date > latest_date):
                latest_date = date
    if not rows:
        raise ValueError("La instantánea de Nomenclátor está vacía.")
    return NomenclatorSnapshot(digest.hexdigest(), len(rows), latest_date, rows)


def load_snapshot(path: Path) -> NomenclatorSnapshot:
    stat = path.stat()
    snapshot = _load_snapshot(str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    expected = path.stem.removeprefix("nomenclatur-").lower()
    if (
        len(expected) == 64
        and all(char in "0123456789abcdef" for char in expected)
        and snapshot.sha256 != expected
    ):
        raise ValueError("El contenido no coincide con el hash del nombre de la instantánea.")
    return snapshot


@dataclass(frozen=True)
class SnapshotChanges:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    modified: tuple[str, ...]


def compare_snapshots(
    previous: NomenclatorSnapshot, current: NomenclatorSnapshot,
) -> SnapshotChanges:
    """Compara por CN las 73 celdas literales; no interpreta ningún valor."""
    old, new = previous.rows, current.rows
    return SnapshotChanges(
        added=tuple(sorted(new.keys() - old.keys())),
        removed=tuple(sorted(old.keys() - new.keys())),
        modified=tuple(sorted(
            cn for cn in new.keys() & old.keys() if new[cn].columns != old[cn].columns
        )),
    )
