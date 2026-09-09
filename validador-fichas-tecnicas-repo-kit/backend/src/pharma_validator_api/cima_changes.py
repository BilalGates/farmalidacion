from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from pharma_validator_api.cima_client import CimaResponse


class CimaChangesError(RuntimeError):
    pass


CHANGE_KINDS = {1: "alta", 2: "baja", 3: "modificacion"}
KNOWN_AREAS = frozenset(
    {"estado", "comerc", "prosp", "ft", "psum", "notasSeguridad", "matinf", "otros"}
)


@dataclass(frozen=True, order=True)
class CimaChange:
    nregistro: str
    occurred_at: int
    change_type: int
    areas: tuple[str, ...]

    @property
    def kind(self) -> str:
        return CHANGE_KINDS[self.change_type]

    @property
    def affects_technical_sheet(self) -> bool:
        return "ft" in self.areas


@dataclass(frozen=True)
class CimaChangeReport:
    requested_date: str
    changes: tuple[CimaChange, ...]
    unknown_areas: tuple[str, ...]
    source_sha256: str
    fetched_at: str


class ChangesClient(Protocol):
    def changes(
        self, *, date: str, nregistros: Sequence[str] = ()
    ) -> CimaResponse: ...


def _requested_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%d/%m/%Y")
    except ValueError as exc:
        raise CimaChangesError("La fecha de registroCambios debe usar dd/mm/yyyy.") from exc
    if parsed.strftime("%d/%m/%Y") != value:
        raise CimaChangesError("La fecha de registroCambios debe usar dd/mm/yyyy.")
    return value


def _non_empty_string(value: Any, *, field: str, index: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CimaChangesError(f"Cambio {index}: {field} debe ser texto no vacío.")
    return value


def parse_change_response(response: CimaResponse, *, requested_date: str) -> CimaChangeReport:
    date = _requested_date(requested_date)
    try:
        payload = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CimaChangesError("registroCambios no devolvió JSON válido.") from exc
    if not isinstance(payload, list):
        raise CimaChangesError("registroCambios debe devolver una lista.")

    parsed: list[CimaChange] = []
    unknown: set[str] = set()
    identities: set[tuple[str, int, int, tuple[str, ...]]] = set()
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise CimaChangesError(f"Cambio {index}: se esperaba un objeto.")
        nregistro = _non_empty_string(
            item.get("nregistro"), field="nregistro", index=index
        )
        occurred_at = item.get("fecha")
        change_type = item.get("tipoCambio")
        areas_value = item.get("cambios")
        if not isinstance(occurred_at, int) or isinstance(occurred_at, bool) or occurred_at < 0:
            raise CimaChangesError(f"Cambio {index}: fecha Epoch incompatible.")
        if change_type not in CHANGE_KINDS:
            raise CimaChangesError(f"Cambio {index}: tipoCambio incompatible.")
        if not isinstance(areas_value, list):
            raise CimaChangesError(f"Cambio {index}: cambios debe ser una lista.")
        areas = tuple(
            sorted(
                {
                    _non_empty_string(area, field="cambios[]", index=index)
                    for area in areas_value
                }
            )
        )
        unknown.update(set(areas) - KNOWN_AREAS)
        identity = (nregistro, occurred_at, change_type, areas)
        if identity in identities:
            continue
        identities.add(identity)
        parsed.append(CimaChange(nregistro, occurred_at, change_type, areas))

    return CimaChangeReport(
        requested_date=date,
        changes=tuple(sorted(parsed)),
        unknown_areas=tuple(sorted(unknown)),
        source_sha256=response.content_sha256,
        fetched_at=response.fetched_at,
    )


def query_cima_changes(
    client: ChangesClient, *, date: str, nregistros: Sequence[str] = ()
) -> CimaChangeReport:
    requested_date = _requested_date(date)
    normalized = tuple(dict.fromkeys(nregistros))
    if any(not item or item != item.strip() for item in normalized):
        raise CimaChangesError("Los nregistros deben ser textos no vacíos sin espacios laterales.")
    response = client.changes(date=requested_date, nregistros=normalized)
    return parse_change_response(response, requested_date=requested_date)
