from __future__ import annotations

import unittest

from scripts.analyze_reference_relationships import RelationSpec, key_result, relation_result


class RelationshipAnalysisTests(unittest.TestCase):
    def test_candidate_requires_complete_unique_values(self) -> None:
        rows = [{"P": "1", "C": "a"}, {"P": "1", "C": "b"}]
        unique = key_result("book", "Child", rows, ("P", "C"))
        repeated = key_result("book", "Child", rows, ("P",))
        self.assertEqual("observed_unique", unique["candidate"])
        self.assertEqual("rejected_by_observation", repeated["candidate"])
        self.assertEqual(1, repeated["duplicate_complete"])

    def test_incomplete_candidate_is_not_accepted(self) -> None:
        result = key_result("book", "Child", [{"ID": "1"}, {"ID": ""}], ("ID",))
        self.assertEqual("rejected_by_observation", result["candidate"])
        self.assertEqual(1, result["incomplete_rows"])

    def test_empty_sheet_does_not_prove_a_key(self) -> None:
        result = key_result("book", "Empty", [], ("ID",))
        self.assertEqual("rejected_by_observation", result["candidate"])

    def test_relation_reports_zero_many_orphans_and_duplicate_parents(self) -> None:
        spec = RelationSpec("r", "book", "General", "Child", ("ID",), ("PARENT_ID",))
        sheets = {
            "General": [{"ID": "1"}, {"ID": "2"}, {"ID": "2"}, {"ID": "3"}],
            "Child": [{"PARENT_ID": "1"}, {"PARENT_ID": "1"}, {"PARENT_ID": "4"}, {"PARENT_ID": ""}],
        }
        result = relation_result(spec, sheets)
        self.assertEqual("0..2", result["observed_cardinality"])
        self.assertEqual(1, result["orphan_rows"])
        self.assertEqual(1, result["orphan_distinct_keys"])
        self.assertEqual(2, result["parents_without_children"])
        self.assertEqual(1, result["parent_duplicate_keys"])
        self.assertEqual(1, result["child_incomplete"])


if __name__ == "__main__":
    unittest.main()
