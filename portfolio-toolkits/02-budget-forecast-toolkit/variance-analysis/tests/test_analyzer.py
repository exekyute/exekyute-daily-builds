"""Tests for the variance analysis tool.

Run from the repository root:
    python -m unittest discover -s variance-analysis/tests -v
"""

import os
import sys
import unittest
from decimal import Decimal

# Make the tool's modules (one directory up) importable.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analyzer import (
    analyze,
    STATUS_FLAGGED,
    STATUS_UNDER,
    STATUS_WITHIN,
)
from loader import parse_amount

PCT = Decimal("10")
DOLLARS = Decimal("5000.00")


def line_for(result, department):
    for line in result.departments:
        if line.department == department:
            return line
    raise AssertionError(f"department {department} not found")


class ParseAmountTests(unittest.TestCase):
    def test_strips_symbols_and_rounds(self):
        self.assertEqual(parse_amount("$1,200.50"), Decimal("1200.50"))
        self.assertEqual(parse_amount("2,999.995"), Decimal("3000.00"))

    def test_blank_or_bad_is_none(self):
        self.assertIsNone(parse_amount(""))
        self.assertIsNone(parse_amount("abc"))


class FlaggingTests(unittest.TestCase):
    def test_percentage_only_breach_is_flagged(self):
        budget = {("Marketing", "Total"): Decimal("6500.00")}
        actual = {("Marketing", "Total"): Decimal("7280.00")}
        result = analyze(budget, actual, PCT, DOLLARS)
        line = line_for(result, "Marketing")
        self.assertEqual(line.variance_pct, Decimal("12.00"))
        self.assertEqual(line.status, STATUS_FLAGGED)

    def test_dollar_only_breach_is_flagged(self):
        budget = {("Sales", "Total"): Decimal("150000.00")}
        actual = {("Sales", "Total"): Decimal("156000.00")}
        result = analyze(budget, actual, PCT, DOLLARS)
        line = line_for(result, "Sales")
        self.assertEqual(line.variance_pct, Decimal("4.00"))
        self.assertEqual(line.status, STATUS_FLAGGED)

    def test_exactly_on_threshold_is_within_parameters(self):
        # Exactly 10% over and exactly 2300 over: neither is strictly greater.
        budget = {("Facilities", "Total"): Decimal("23000.00")}
        actual = {("Facilities", "Total"): Decimal("25300.00")}
        result = analyze(budget, actual, PCT, DOLLARS)
        line = line_for(result, "Facilities")
        self.assertEqual(line.variance_pct, Decimal("10.00"))
        self.assertEqual(line.status, STATUS_WITHIN)
        self.assertEqual(result.flagged, [])

    def test_under_budget_is_not_flagged(self):
        budget = {("Research", "Total"): Decimal("25000.00")}
        actual = {("Research", "Total"): Decimal("22500.00")}
        result = analyze(budget, actual, PCT, DOLLARS)
        line = line_for(result, "Research")
        self.assertEqual(line.status, STATUS_UNDER)


class FindingsTests(unittest.TestCase):
    def test_missing_and_unbudgeted_line_items(self):
        budget = {
            ("Sales", "Commissions"): Decimal("90000.00"),
            ("Sales", "Software"): Decimal("1250.00"),
        }
        actual = {
            ("Sales", "Commissions"): Decimal("94000.00"),
            ("Operations", "Software"): Decimal("2000.00"),
        }
        result = analyze(budget, actual, PCT, DOLLARS)
        self.assertIn(("Sales", "Software"), result.missing_from_actuals)
        self.assertIn(("Operations", "Software"), result.unbudgeted)


if __name__ == "__main__":
    unittest.main()
