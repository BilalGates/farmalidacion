from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import profile_reference_files as profiler

CONTENT_TYPES = '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'''
ROOT_RELS = '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
WORKBOOK = '''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="General" sheetId="1" r:id="rId1"/><sheet name="Child" sheetId="2" r:id="rId2"/></sheets></workbook>'''
WORKBOOK_RELS = '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>'''
SHEET_GENERAL = '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:B3"/><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c><c r="B1" t="inlineStr"><is><t>VALUE</t></is></c></row><row r="2"><c r="A2"><v>1</v></c><c r="B2" t="inlineStr"><is><t>=literal</t></is></c></row><row r="3"><c r="A3" s="1"/></row></sheetData></worksheet>'''
SHEET_CHILD = '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:B3"/><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>PARENT_ID</t></is></c><c r="B1" t="inlineStr"><is><t>ITEM</t></is></c></row><row r="2"><c r="A2"><v>1</v></c><c r="B2" t="inlineStr"><is><t>first</t></is></c></row><row r="3"><c r="A3"><v>2</v></c><c r="B3" t="inlineStr"><is><t>second</t></is></c></row></sheetData></worksheet>'''


def make_workbook(path: Path) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in (("[Content_Types].xml", CONTENT_TYPES), ("_rels/.rels", ROOT_RELS), ("xl/workbook.xml", WORKBOOK), ("xl/_rels/workbook.xml.rels", WORKBOOK_RELS), ("xl/worksheets/sheet1.xml", SHEET_GENERAL), ("xl/worksheets/sheet2.xml", SHEET_CHILD)):
            archive.writestr(name, content)


class ProfilerUnitTests(unittest.TestCase):
    def test_csv_formula_prefix_is_encoded_without_losing_original(self) -> None:
        encoded, changed = profiler.csv_safe("=SUM(A1:A2)")
        self.assertEqual("'=SUM(A1:A2)", encoded)
        self.assertTrue(changed)

    def test_zip_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../escape.xml", "bad")
            with self.assertRaises(profiler.ProfilingError):
                profiler.validate_xlsx(path)

    def test_printer_settings_are_inert_but_macros_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            safe = Path(directory) / "printer.xlsx"
            with zipfile.ZipFile(safe, "w") as archive:
                archive.writestr("xl/printerSettings/printerSettings1.bin", b"printer")
            profiler.validate_xlsx(safe)
            unsafe = Path(directory) / "macro.xlsx"
            with zipfile.ZipFile(unsafe, "w") as archive:
                archive.writestr("xl/vbaProject.bin", b"macro")
            with self.assertRaises(profiler.ProfilingError):
                profiler.validate_xlsx(unsafe)

    def test_column_conversion_round_trip(self) -> None:
        for index in (1, 26, 27, 702, 703):
            self.assertEqual(index, profiler.column_index(profiler.column_letter(index) + "9"))


class ProfilerIntegrationTests(unittest.TestCase):
    def test_aggregate_profile_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw"
            raw.mkdir()
            name = "fixture.xlsx"
            workbook = raw / name
            make_workbook(workbook)
            digest = hashlib.sha256(workbook.read_bytes()).hexdigest()
            with patch.object(profiler, "XLSX_NAMES", (name,)), patch.object(profiler, "EXPECTED", {name: digest}), patch.object(profiler, "WORKBOOK_IDS", {name: "fixture"}):
                first = profiler.run_profile(raw, root / "one")
                second = profiler.run_profile(raw, root / "two")
            self.assertEqual(first["reproducible_content_hash"], second["reproducible_content_hash"])
            payload = json.loads((root / "one" / "workbooks" / "fixture.json").read_text(encoding="utf-8"))
            general = payload["sheets"][0]
            self.assertEqual(2, general["material_rows"])
            self.assertNotIn("cells", general)
            self.assertEqual("deferred_to_DEV004_DEV006", payload["relations_detail"])
            with (root / "one" / "columns.csv").open(encoding="utf-8", newline="") as handle:
                columns = list(csv.DictReader(handle))
            self.assertEqual(4, len(columns))


if __name__ == "__main__":
    unittest.main()
