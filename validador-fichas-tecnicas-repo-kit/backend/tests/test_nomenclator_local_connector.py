"""El conector de escritorio sólo consulta la tabla y conserva sus 73 celdas."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import nomenclator_local_connector as connector


class FakeCursor:
    def __init__(self, *, valid_schema: bool = True) -> None:
        names = [f"col{i}" for i in range(73)]
        for index, name in connector.EXPECTED_COLUMNS.items():
            names[index] = name
        if not valid_schema:
            names[48] = "otra_columna"
        self.description = [(name,) for name in names]
        self.query = ""
        self.called = False

    def execute(self, query: str) -> None:
        self.query = query

    def fetchmany(self, _: int) -> list[tuple[str, ...]]:
        if self.called:
            return []
        self.called = True
        columns = [""] * 73
        columns[0], columns[1], columns[48] = "1", "600000", "J01CR02"
        return [tuple(columns)]

    def close(self) -> None:
        pass


def test_local_connector_uses_windows_identity_and_only_nomenclatur(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = FakeCursor()
    options: dict[str, object] = {}

    def connect(**values: object) -> SimpleNamespace:
        options.update(values)
        return SimpleNamespace(cursor=lambda: cursor, close=lambda: None)

    monkeypatch.setattr(connector, "import_module", lambda _: SimpleNamespace(connect=connect))
    path = tmp_path / "copy.tsv"
    digest, count = connector.export_snapshot({
        "server": "localhost", "port": 1433, "database": "DICCIONARIOS", "auth": "windows",
    }, path)
    assert count == 1
    assert len(digest) == 64
    assert options["trusted_connection"] == "yes"
    assert options["encrypt"] == "yes"
    assert "pwd" not in options
    assert cursor.query.startswith("SELECT * FROM [dbo].[nomenclatur]")
    assert path.read_text(encoding="utf-8").split("\t")[1] == "600000"


def test_local_connector_can_disable_encryption_when_server_requires_it() -> None:
    options = connector._connection_options({
        "server": "localhost", "port": 0, "database": "DICCIONARIOS",
        "auth": "windows", "encrypt": False,
    })
    assert options["server"] == "localhost"
    assert options["encrypt"] == "no"


def test_local_connector_rejects_schema_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = FakeCursor(valid_schema=False)
    monkeypatch.setattr(connector, "import_module", lambda _: SimpleNamespace(
        connect=lambda **_: SimpleNamespace(cursor=lambda: cursor, close=lambda: None),
    ))
    path = tmp_path / "copy.tsv"
    with pytest.raises(ValueError, match="columna 49"):
        connector.export_snapshot({
            "server": "localhost", "port": 1433, "database": "DICCIONARIOS",
            "auth": "windows",
        }, path)
    assert not path.exists()
