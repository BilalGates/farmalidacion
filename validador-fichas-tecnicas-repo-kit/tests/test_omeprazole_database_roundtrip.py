from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from test_profile_reference_files import make_workbook

from scripts.roundtrip_omeprazole_database import run_database_roundtrip


class OmeprazoleDatabaseRoundTripTests(unittest.TestCase):
    def test_temporary_application_schema_roundtrips_every_source_cell(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fixture.xlsx"
            destination = root / "reconstructed.xlsx"
            make_workbook(source)
            expected_hash = hashlib.sha256(source.read_bytes()).hexdigest()

            evidence = run_database_roundtrip(
                source,
                destination,
                expected_hash,
                {
                    "General": ("medicamento", "general"),
                    "Child": ("medicamento", "child"),
                },
            )

        self.assertEqual("pass", evidence["status"])
        self.assertEqual(0, evidence["difference_count"])
        self.assertEqual(2, evidence["sheets_compared"])
        self.assertEqual(5, evidence["persisted"]["target_records"])
        self.assertEqual(10, evidence["persisted"]["field_values"])


if __name__ == "__main__":
    unittest.main()
