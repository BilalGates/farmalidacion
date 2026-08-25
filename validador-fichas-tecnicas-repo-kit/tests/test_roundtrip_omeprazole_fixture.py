from __future__ import annotations

import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.roundtrip_omeprazole_fixture import compare_packages, run_roundtrip
from test_profile_reference_files import make_workbook


class OmeprazoleRoundTripTests(unittest.TestCase):
    roles = {"General": ("medicamento", "general"), "Child": ("medicamento", "child")}

    def test_roundtrip_is_lossless_and_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fixture.xlsx"
            make_workbook(source)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            first = run_roundtrip(source, root / "one", digest, self.roles)
            second = run_roundtrip(source, root / "two", digest, self.roles)
        self.assertEqual("pass", first["status"])
        self.assertEqual(0, first["difference_count"])
        self.assertEqual(first["reproducible_content_hash"], second["reproducible_content_hash"])

    def test_mutated_output_is_reported_as_defect(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fixture.xlsx"
            make_workbook(source)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            run_roundtrip(source, root / "run", digest, self.roles)
            output = root / "run" / "reconstructed.xlsx"
            mutated = root / "mutated.xlsx"
            with zipfile.ZipFile(output) as original, zipfile.ZipFile(mutated, "w") as changed:
                for info in original.infolist():
                    payload = original.read(info.filename)
                    if info.filename == "xl/worksheets/sheet1.xml":
                        payload = payload.replace(b">1</", b">9</", 1)
                    changed.writestr(info, payload)
            differences, _sheets = compare_packages(source, mutated)
        self.assertTrue(any(item["category"] == "defect" for item in differences))


if __name__ == "__main__":
    unittest.main()
