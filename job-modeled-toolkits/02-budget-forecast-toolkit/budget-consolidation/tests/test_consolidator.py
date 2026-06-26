"""Tests for the budget consolidation tool.

Run from the repository root:
    python -m unittest discover -s budget-consolidation/tests -v
"""

import os
import sys
import unittest
from decimal import Decimal

# Make the tool's modules (one directory up) importable.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from consolidator import (
    consolidate,
    format_amount,
    standardize_amount,
    standardize_category,
)
from loader import department_name_from_path


class StandardizeAmountTests(unittest.TestCase):
    def test_strips_currency_symbol_and_commas(self):
        self.assertEqual(standardize_amount("$1,200.50"), Decimal("1200.50"))

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(standardize_amount(" 4300 "), Decimal("4300.00"))

    def test_rounds_half_up_at_the_boundary(self):
        self.assertEqual(standardize_amount("2,999.995"), Decimal("3000.00"))
        self.assertEqual(standardize_amount("100.005"), Decimal("100.01"))
        self.assertEqual(standardize_amount("2.675"), Decimal("2.68"))

    def test_blank_returns_none(self):
        self.assertIsNone(standardize_amount(""))
        self.assertIsNone(standardize_amount("   "))

    def test_non_numeric_returns_none(self):
        self.assertIsNone(standardize_amount("abc"))


class StandardizeCategoryTests(unittest.TestCase):
    def test_title_cases_and_collapses_spaces(self):
        self.assertEqual(standardize_category("  office   supplies "), "Office Supplies")
        self.assertEqual(standardize_category("EVENTS"), "Events")


class DepartmentNameTests(unittest.TestCase):
    def test_name_from_file_stem(self):
        self.assertEqual(department_name_from_path("data/sales.csv"), "Sales")
        self.assertEqual(
            department_name_from_path("human_resources.csv"), "Human Resources"
        )


class ConsolidateTests(unittest.TestCase):
    def test_merges_duplicate_categories_within_a_department(self):
        departments = [
            (
                "Operations",
                [
                    {"category": "Travel", "amount": "3200.00"},
                    {"category": "Travel", "amount": "1800.00"},
                ],
            )
        ]
        result = consolidate(departments)
        self.assertEqual(result.duplicates_merged, 1)
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0]["amount"], Decimal("5000.00"))

    def test_skips_blank_category_and_bad_amount(self):
        departments = [
            (
                "Facilities",
                [
                    {"category": "Rent", "amount": "20000.00"},
                    {"category": "", "amount": "500.00"},
                    {"category": "Security", "amount": ""},
                    {"category": "Power", "amount": "abc"},
                ],
            )
        ]
        result = consolidate(departments)
        self.assertEqual(result.skipped_blank_category, 1)
        self.assertEqual(result.skipped_bad_amount, 2)
        self.assertEqual(result.line_items, 1)

    def test_rows_sorted_by_department_then_category(self):
        departments = [
            ("Sales", [{"category": "Travel", "amount": "10.00"}]),
            ("Facilities", [{"category": "Rent", "amount": "20.00"}]),
            ("Sales", [{"category": "Commissions", "amount": "30.00"}]),
        ]
        result = consolidate(departments)
        ordered = [(r["department"], r["category"]) for r in result.rows]
        self.assertEqual(
            ordered,
            [("Facilities", "Rent"), ("Sales", "Commissions"), ("Sales", "Travel")],
        )


class FormatAmountTests(unittest.TestCase):
    def test_fixed_point_never_scientific(self):
        self.assertEqual(format_amount(Decimal("1250")), "1250.00")
        self.assertEqual(format_amount(Decimal("0")), "0.00")
        self.assertNotIn("E", format_amount(Decimal("100000000")))


if __name__ == "__main__":
    unittest.main()
