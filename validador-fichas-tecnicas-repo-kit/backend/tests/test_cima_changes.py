import hashlib
import json
from dataclasses import dataclass

import pytest

from pharma_validator_api.cima_changes import (
    CimaChangesError,
    parse_change_response,
    query_cima_changes,
)
from pharma_validator_api.cima_client import CimaResponse


def response(payload: object) -> CimaResponse:
    body = json.dumps(payload).encode()
    return CimaResponse(
        url="https://cima.example.test/rest/registroCambios?fecha=09%2F09%2F2026",
        status_code=200,
        headers=(("Content-Type", "application/json"),),
        body=body,
        content_sha256=hashlib.sha256(body).hexdigest(),
        fetched_at="2026-09-09T08:00:00+00:00",
        from_cache=False,
    )


def test_parses_all_change_kinds_and_preserves_unknown_areas() -> None:
    report = parse_change_response(
        response(
            [
                {"nregistro": "B", "fecha": 2, "tipoCambio": 3, "cambios": ["ft", "nuevo"]},
                {"nregistro": "A", "fecha": 1, "tipoCambio": 1, "cambios": ["estado"]},
                {"nregistro": "C", "fecha": 3, "tipoCambio": 2, "cambios": []},
            ]
        ),
        requested_date="09/09/2026",
    )

    assert [item.kind for item in report.changes] == ["alta", "modificacion", "baja"]
    assert report.changes[1].affects_technical_sheet is True
    assert report.unknown_areas == ("nuevo",)


def test_duplicate_rows_and_areas_have_a_stable_representation() -> None:
    item = {"nregistro": "1", "fecha": 7, "tipoCambio": 3, "cambios": ["ft", "ft"]}
    report = parse_change_response(response([item, item]), requested_date="01/01/2026")

    assert len(report.changes) == 1
    assert report.changes[0].areas == ("ft",)


def test_parses_live_paginated_wrapper_and_singular_change_key() -> None:
    report = parse_change_response(
        response(
            {
                "totalFilas": 1,
                "pagina": 1,
                "tamanioPagina": 200,
                "resultados": [{"nregistro": "1", "fecha": 7, "tipoCambio": 3, "cambio": ["ft"]}],
            }
        ),
        requested_date="09/09/2026",
    )
    assert report.changes[0].areas == ("ft",)


@pytest.mark.parametrize(
    "payload, message",
    [
        ({}, "lista"),
        ([{"nregistro": "", "fecha": 1, "tipoCambio": 3, "cambios": []}], "nregistro"),
        ([{"nregistro": "1", "fecha": "1", "tipoCambio": 3, "cambios": []}], "Epoch"),
        ([{"nregistro": "1", "fecha": 1, "tipoCambio": 9, "cambios": []}], "tipoCambio"),
        ([{"nregistro": "1", "fecha": 1, "tipoCambio": 3, "cambios": "ft"}], "lista"),
    ],
)
def test_incompatible_shapes_fail_visibly(payload: object, message: str) -> None:
    with pytest.raises(CimaChangesError, match=message):
        parse_change_response(response(payload), requested_date="09/09/2026")


@dataclass
class StubClient:
    calls: list[tuple[str, tuple[str, ...]]]

    def changes(self, *, date: str, nregistros: tuple[str, ...] = ()) -> CimaResponse:
        self.calls.append((date, nregistros))
        return response([])


def test_query_validates_date_and_deduplicates_filters_without_reordering() -> None:
    client = StubClient([])
    report = query_cima_changes(client, date="09/09/2026", nregistros=("51347", "99999", "51347"))

    assert report.changes == ()
    assert client.calls == [("09/09/2026", ("51347", "99999"))]
    with pytest.raises(CimaChangesError, match="dd/mm/yyyy"):
        query_cima_changes(client, date="2026-09-09")
