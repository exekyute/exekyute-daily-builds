"""Tests for the field audit validator's core logic.

These check each validator with both a good value and a bad value, and check that
a finished entry is formatted into one clean, timestamped line. The timestamp is
passed in, so the test is deterministic and does not depend on the clock.

Run from the tool folder with:
    python -m unittest discover tests
"""

import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core


class TestText(unittest.TestCase):
    def test_accepts_value(self):
        value, error = core.validate_text("  Jane Smith ")
        self.assertEqual(value, "Jane Smith")
        self.assertIsNone(error)

    def test_rejects_blank(self):
        value, error = core.validate_text("   ")
        self.assertIsNone(value)
        self.assertIsNotNone(error)


class TestDate(unittest.TestCase):
    def test_accepts_iso_date(self):
        value, error = core.validate_date("2026-06-06")
        self.assertEqual(value, "2026-06-06")
        self.assertIsNone(error)

    def test_rejects_slash_format(self):
        value, error = core.validate_date("06/06/2026")
        self.assertIsNone(value)
        self.assertIsNotNone(error)

    def test_rejects_impossible_date(self):
        value, error = core.validate_date("2026-02-30")
        self.assertIsNone(value)
        self.assertIsNotNone(error)


class TestNumber(unittest.TestCase):
    def test_accepts_number(self):
        value, error = core.validate_number("12.5")
        self.assertEqual(value, Decimal("12.5"))
        self.assertIsNone(error)

    def test_accepts_zero(self):
        value, error = core.validate_number("0")
        self.assertEqual(value, Decimal("0"))
        self.assertIsNone(error)

    def test_rejects_negative(self):
        value, error = core.validate_number("-3")
        self.assertIsNone(value)
        self.assertIsNotNone(error)

    def test_rejects_non_number(self):
        value, error = core.validate_number("full")
        self.assertIsNone(value)
        self.assertIsNotNone(error)


class TestChoice(unittest.TestCase):
    def test_accepts_any_case(self):
        value, error = core.validate_choice("north", ["NORTH", "HARBOR", "RIDGE"])
        self.assertEqual(value, "NORTH")
        self.assertIsNone(error)

    def test_rejects_unlisted(self):
        value, error = core.validate_choice("east", ["NORTH", "HARBOR", "RIDGE"])
        self.assertIsNone(value)
        self.assertIsNotNone(error)


class TestFormatRecord(unittest.TestCase):
    def setUp(self):
        self.questions = [
            {"key": "site_code", "type": "choice", "choices": ["NORTH"]},
            {"key": "inspection_date", "type": "date"},
            {"key": "inspector", "type": "text"},
            {"key": "fuel_reading", "type": "number"},
            {"key": "result", "type": "choice", "choices": ["PASS", "FAIL"]},
            {"key": "notes", "type": "text"},
        ]
        self.answers = {
            "site_code": "NORTH",
            "inspection_date": "2026-06-05",
            "inspector": "Jane Smith",
            "fuel_reading": Decimal("12.5"),
            "result": "PASS",
            "notes": "all clear",
        }

    def test_line_has_timestamp_first_and_fixed_point_number(self):
        line = core.format_record(self.questions, self.answers, "2026-06-06 14:30:00")
        self.assertTrue(line.startswith("2026-06-06 14:30:00 | "))
        self.assertIn(" | 12.50 | ", line)
        self.assertEqual(line.count(" | "), 6)

    def test_free_text_pipes_are_neutralised(self):
        self.answers["notes"] = "leak | near pump"
        line = core.format_record(self.questions, self.answers, "2026-06-06 14:30:00")
        # The stray pipe in the note must not add an extra column.
        self.assertEqual(line.count(" | "), 6)


if __name__ == "__main__":
    unittest.main()
