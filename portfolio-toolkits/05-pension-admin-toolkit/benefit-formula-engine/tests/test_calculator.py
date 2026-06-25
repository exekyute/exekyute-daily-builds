"""Tests for the Benefit Formula Engine.

Run from the repository root:
    python -m unittest discover -s benefit-formula-engine/tests -v

The sys.path line lets this test file import the engine modules that sit one
folder up. Without it, Python would not know where to find calculator.py.
"""

import os
import sys
import unittest
from decimal import Decimal

# Make the engine modules (one directory up) importable.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from plan_rules import DEFAULT_PLAN
from calculator import (
    final_average_earnings,
    gross_annual_pension,
    early_reduction_fraction,
    calculate_benefit,
)
from validators import (
    ValidationError,
    validate_salary_history,
    validate_years_of_service,
    validate_retirement_age,
)


class TestFinalAverageEarnings(unittest.TestCase):
    def test_takes_highest_n_years(self):
        salaries = [Decimal(x) for x in ("70000", "80000", "90000", "100000", "110000", "120000")]
        # Best 5 of 6: 80k, 90k, 100k, 110k, 120k -> average 100k.
        result = final_average_earnings(salaries, DEFAULT_PLAN)
        self.assertEqual(result, Decimal("100000.00"))


class TestEarlyReduction(unittest.TestCase):
    def test_no_reduction_at_normal_age(self):
        self.assertEqual(early_reduction_fraction(65, DEFAULT_PLAN), Decimal("0"))

    def test_no_reduction_after_normal_age(self):
        self.assertEqual(early_reduction_fraction(67, DEFAULT_PLAN), Decimal("0"))

    def test_reduction_scales_with_years_early(self):
        # Five years early at 6 percent per year is a 30 percent reduction.
        self.assertEqual(early_reduction_fraction(60, DEFAULT_PLAN), Decimal("0.30"))


class TestFullCalculation(unittest.TestCase):
    def test_normal_retirement_no_reduction(self):
        salaries = [Decimal("100000")] * 5
        result = calculate_benefit(salaries, 30, False, 65, DEFAULT_PLAN)
        # 2% * 30 * 100000 = 60000 gross, no reduction, 5000 per month.
        self.assertEqual(result.gross_annual, Decimal("60000.00"))
        self.assertEqual(result.net_annual, Decimal("60000.00"))
        self.assertEqual(result.monthly_payout, Decimal("5000.00"))

    def test_early_retirement_applies_reduction(self):
        salaries = [Decimal("100000")] * 5
        result = calculate_benefit(salaries, 30, False, 60, DEFAULT_PLAN)
        # 60000 gross reduced 30% -> 42000 net -> 3500 per month.
        self.assertEqual(result.net_annual, Decimal("42000.00"))
        self.assertEqual(result.monthly_payout, Decimal("3500.00"))


class TestServiceCap(unittest.TestCase):
    def test_service_above_max_is_clamped(self):
        credited, was_capped = validate_years_of_service(40, DEFAULT_PLAN)
        self.assertEqual(credited, DEFAULT_PLAN.max_credited_service)
        self.assertTrue(was_capped)

    def test_service_within_limit_is_unchanged(self):
        credited, was_capped = validate_years_of_service(30, DEFAULT_PLAN)
        self.assertEqual(credited, 30)
        self.assertFalse(was_capped)


class TestValidationRejectsBadInput(unittest.TestCase):
    def test_negative_salary_rejected(self):
        with self.assertRaises(ValidationError):
            validate_salary_history(["80000", "-5", "81000", "82000", "83000"], DEFAULT_PLAN)

    def test_non_numeric_salary_rejected(self):
        with self.assertRaises(ValidationError):
            validate_salary_history(["80000", "abc", "81000", "82000", "83000"], DEFAULT_PLAN)

    def test_too_few_salary_years_rejected(self):
        with self.assertRaises(ValidationError):
            validate_salary_history(["80000", "81000", "82000"], DEFAULT_PLAN)

    def test_age_below_earliest_rejected(self):
        with self.assertRaises(ValidationError):
            validate_retirement_age(50, DEFAULT_PLAN)

    def test_zero_years_of_service_rejected(self):
        with self.assertRaises(ValidationError):
            validate_years_of_service(0, DEFAULT_PLAN)


if __name__ == "__main__":
    unittest.main()
