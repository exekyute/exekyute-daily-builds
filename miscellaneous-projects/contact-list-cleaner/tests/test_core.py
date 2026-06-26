"""Tests for the cleaning functions in core.py.

These use Python's built-in `unittest`, so there is nothing to install. Run them
from the project folder with:

    python -m unittest discover tests

Each test states what it expects in plain English. Tests are the safety net that
lets you change core.py later and instantly see if you broke something.
"""

import os
import sys
import unittest

# Make sure we can import core.py, which lives one folder up from this file.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core  # noqa: E402  (import after the path tweak above)


class TestNormalizeName(unittest.TestCase):
    def test_caps_and_spaces(self):
        self.assertEqual(core.normalize_name("  JOHN   DOE "), "John Doe")

    def test_empty(self):
        self.assertEqual(core.normalize_name(""), "")


class TestNormalizeEmail(unittest.TestCase):
    def test_lowercases_and_trims(self):
        self.assertEqual(core.normalize_email("  Jane@Acme.com "), "jane@acme.com")

    def test_pulls_address_from_angle_brackets(self):
        self.assertEqual(
            core.normalize_email("Jane Doe <jane@acme.com>"), "jane@acme.com")

    def test_empty(self):
        self.assertEqual(core.normalize_email(""), "")


class TestNormalizePhone(unittest.TestCase):
    def test_formats_ten_digits(self):
        self.assertEqual(core.normalize_phone("555.123.4567"), ("(555) 123-4567", True))

    def test_drops_leading_country_code(self):
        self.assertEqual(
            core.normalize_phone("+1 (555) 123-4567"), ("(555) 123-4567", True))

    def test_short_number_is_flagged(self):
        # Too short to be real: returned as bare digits, marked invalid.
        self.assertEqual(core.normalize_phone("555-12"), ("55512", False))

    def test_empty_is_valid(self):
        self.assertEqual(core.normalize_phone(""), ("", True))


class TestMatchKey(unittest.TestCase):
    def test_email_wins(self):
        c = core.normalize_contact(
            {"name": "Jane", "email": "jane@acme.com", "phone": "5551234567"})
        self.assertEqual(core.match_key(c), "email:jane@acme.com")

    def test_falls_back_to_phone(self):
        c = core.normalize_contact(
            {"name": "Bob", "email": "", "phone": "555.234.5678"})
        self.assertEqual(core.match_key(c), "phone:(555) 234-5678")

    def test_falls_back_to_name(self):
        c = core.normalize_contact({"name": "Carol King", "email": "", "phone": ""})
        self.assertEqual(core.match_key(c), "name:carol king")

    def test_blank_row_gets_unique_key(self):
        c = core.normalize_contact({"name": "", "email": "", "phone": ""})
        self.assertEqual(core.match_key(c, fallback_id=7), "row:7")


class TestMergeGroup(unittest.TestCase):
    def test_fills_blanks_from_siblings(self):
        rows = [
            core.normalize_contact(
                {"name": "Jane Doe", "email": "jane@acme.com",
                 "phone": "", "company": "Acme", "title": "Lead"}),
            core.normalize_contact(
                {"name": "Jane Doe", "email": "jane@acme.com",
                 "phone": "5551234567", "company": "", "title": ""}),
        ]
        merged, conflicts = core.merge_group(rows)
        self.assertEqual(merged["phone"], "(555) 123-4567")  # filled from row 2
        self.assertEqual(merged["company"], "Acme")          # filled from row 1
        self.assertEqual(conflicts, [])

    def test_records_a_conflict_on_disagreement(self):
        rows = [
            core.normalize_contact(
                {"name": "Dave", "email": "dave@x.com", "company": "Umbrella Media"}),
            core.normalize_contact(
                {"name": "Dave", "email": "dave@x.com", "company": "Umbrella Corp"}),
        ]
        merged, conflicts = core.merge_group(rows)
        self.assertEqual(merged["company"], "Umbrella Media")  # keeps the first
        self.assertEqual(
            conflicts, [("company", ["Umbrella Media", "Umbrella Corp"])])


class TestPlanClean(unittest.TestCase):
    def test_dedupes_and_counts(self):
        rows = [
            {"name": "Jane", "email": "Jane@Acme.com", "phone": ""},
            {"name": "jane", "email": "jane@acme.com", "phone": "5551234567"},
            {"name": "Grace", "email": "grace@globex.com", "phone": "5554567890"},
        ]
        plan = core.plan_clean(rows)
        self.assertEqual(plan.rows_in, 3)
        self.assertEqual(plan.rows_out, 2)              # the two Janes merged
        self.assertEqual(len(plan.merged_groups), 1)

    def test_invalid_phone_is_surfaced(self):
        rows = [{"name": "Frank", "email": "frank@x.com", "phone": "555-12"}]
        plan = core.plan_clean(rows)
        self.assertEqual(len(plan.invalid_phones), 1)
        self.assertEqual(plan.invalid_phones[0]["phone"], "55512")


if __name__ == "__main__":
    unittest.main()
