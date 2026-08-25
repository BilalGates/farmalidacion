from __future__ import annotations
import unittest
from scripts.analyze_integrity_incidents import parse_char_limit

class IntegrityIncidentTests(unittest.TestCase):
    def test_char_limit_accepts_catalog_spacing(self):
        self.assertEqual(100, parse_char_limit("CHAR(100)"))
        self.assertEqual(1, parse_char_limit("CHAR (1)"))
    def test_non_char_has_no_length_limit(self):
        self.assertIsNone(parse_char_limit("ENTERO >=0"))
        self.assertIsNone(parse_char_limit("DECIMAL (10, 3) >=0"))

if __name__ == "__main__": unittest.main()
