from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.import_omeprazole_fixture import FixtureImportError, build_snapshot, run_import
from test_profile_reference_files import make_workbook


class OmeprazoleFixtureImportTests(unittest.TestCase):
    def test_snapshot_preserves_material_rows_values_and_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "fixture.xlsx"
            make_workbook(source)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            roles = {"General": ("medicamento", "general"), "Child": ("medicamento", "child")}
            snapshot = build_snapshot(source, digest, roles)
        self.assertEqual(2, snapshot["totals"]["sheets"])
        self.assertEqual(5, snapshot["totals"]["material_rows"])
        self.assertEqual(10, snapshot["totals"]["material_values"])
        self.assertEqual("A1", snapshot["sheets"][0]["occurrences"][0]["values"][0]["coordinate"])
        self.assertEqual("technical_provisional_not_natural_key", snapshot["sheets"][0]["occurrences"][0]["occurrence_identity"])

    def test_repeated_import_produces_same_canonical_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fixture.xlsx"
            make_workbook(source)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            roles = {"General": ("medicamento", "general"), "Child": ("medicamento", "child")}
            first = run_import(source, root / "one", digest, roles)
            second = run_import(source, root / "two", digest, roles)
        self.assertEqual(first["canonical_content_hash"], second["canonical_content_hash"])

    def test_sheet_order_must_match_explicit_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "fixture.xlsx"
            make_workbook(source)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaises(FixtureImportError):
                build_snapshot(source, digest, {"Child": ("x", "y"), "General": ("x", "z")})


if __name__ == "__main__":
    unittest.main()
