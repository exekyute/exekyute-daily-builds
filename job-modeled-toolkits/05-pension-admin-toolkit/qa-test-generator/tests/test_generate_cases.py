"""Tests for the QA Test-Case Generator.

Run from the repository root:
    python -m unittest discover -s qa-test-generator/tests -v

These tests confirm the generator drives the real Benefit Engine correctly: the
worked example matches the hand calculation in the engine's spec, the cap and
reduction scenarios behave, and the invalid scenarios are actually rejected.
"""

import os
import sys
import unittest

# Make the generator module (one directory up) importable.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from generate_cases import generate, to_markdown


def by_name(records):
    return {record["name"]: record for record in records}


class TestGenerate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = generate()
        cls.indexed = by_name(cls.records)

    def test_every_scenario_behaved_as_expected(self):
        # The generator's own pass flag should be true for all bundled scenarios.
        self.assertTrue(all(record["passed"] for record in self.records))

    def test_worked_example_matches_engine_spec(self):
        # Normal retirement at 65 with 30 years and $100k must be $5,000.00 / month.
        record = self.indexed["Normal retirement at 65"]
        self.assertEqual(record["expected_monthly"], "5000.00")

    def test_max_reduction_at_age_55(self):
        # Ten years early at 6 percent is 60 percent off: 60000 -> 24000 -> 2000 / month.
        record = self.indexed["Early retirement at 55"]
        self.assertEqual(record["expected_monthly"], "2000.00")

    def test_service_cap_scenario_is_flagged_capped(self):
        record = self.indexed["Service above the cap"]
        self.assertIn("capped", record["detail"])

    def test_invalid_scenarios_are_rejected(self):
        for name in ("Invalid: negative salary rejected", "Invalid: age below earliest rejected"):
            record = self.indexed[name]
            self.assertEqual(record["outcome"], "rejected")
            self.assertIsNone(record["expected_monthly"])

    def test_markdown_has_a_row_per_scenario(self):
        markdown = to_markdown(self.records)
        for record in self.records:
            self.assertIn(record["name"], markdown)


if __name__ == "__main__":
    unittest.main()
