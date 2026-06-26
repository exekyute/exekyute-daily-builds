"""Unit tests for the Canadian payroll calculator.

Run from the repository root:
    python -m unittest discover -s 09-payroll-ops-toolkit/01-payroll-run-calculator/tests

Or from this tool's folder:
    python -m unittest discover -s tests

The path insert below lets the tests import the tool modules no matter which
directory the test runner is launched from.
"""

import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import payroll_logic as logic
import payroll_validation as validation


def D(value):
    return Decimal(value)


class GrossPayTests(unittest.TestCase):
    def setUp(self):
        self.config = logic.PayrollConfig()

    def test_salaried_has_no_overtime(self):
        gross, overtime = logic.gross_pay("salaried", "2500.00", "0", self.config)
        self.assertEqual(gross, D("2500.00"))
        self.assertEqual(overtime, D("0.00"))

    def test_hourly_under_threshold_has_no_overtime(self):
        gross, overtime = logic.gross_pay("hourly", "25.00", "38", self.config)
        self.assertEqual(gross, D("950.00"))
        self.assertEqual(overtime, D("0.00"))

    def test_hourly_over_threshold_applies_overtime(self):
        # 44 regular hours at 30, plus 6 overtime hours at 1.5x.
        gross, overtime = logic.gross_pay("hourly", "30.00", "50", self.config)
        self.assertEqual(overtime, D("270.00"))
        self.assertEqual(gross, D("1590.00"))

    def test_zero_hours_is_a_valid_boundary(self):
        gross, overtime = logic.gross_pay("hourly", "22.00", "0", self.config)
        self.assertEqual(gross, D("0.00"))
        self.assertEqual(overtime, D("0.00"))


class StatutoryDeductionTests(unittest.TestCase):
    def setUp(self):
        self.config = logic.PayrollConfig()

    def test_cpp_below_cap(self):
        # (1590 - 3500/26) * 0.0595 = 86.595..., rounds to 86.60.
        self.assertEqual(logic.cpp_contribution(D("1590.00"), self.config), D("86.60"))

    def test_cpp_capped_for_high_earner(self):
        # Per-period cap is 3867.50 / 26 = 148.75.
        self.assertEqual(logic.cpp_contribution(D("8000.00"), self.config), D("148.75"))

    def test_cpp_zero_when_below_exemption(self):
        self.assertEqual(logic.cpp_contribution(D("0.00"), self.config), D("0.00"))

    def test_ei_below_cap(self):
        # 950 * 0.0166 = 15.77.
        self.assertEqual(logic.ei_premium(D("950.00"), self.config), D("15.77"))

    def test_ei_capped_for_high_earner(self):
        # Per-period cap is 1049.12 / 26 = 40.35 (rounded).
        self.assertEqual(logic.ei_premium(D("8000.00"), self.config), D("40.35"))

    def test_income_tax_uses_taxable_after_pretax(self):
        # (1590 - 50) * 0.20 = 308.00.
        self.assertEqual(logic.income_tax(D("1590.00"), D("50.00"), self.config), D("308.00"))

    def test_income_tax_zero_when_pretax_exceeds_gross(self):
        self.assertEqual(logic.income_tax(D("100.00"), D("200.00"), self.config), D("0.00"))


class CalculatePayTests(unittest.TestCase):
    def setUp(self):
        self.config = logic.PayrollConfig()

    def test_hand_checked_hourly_overtime_employee(self):
        employee = {
            "employee_id": "E002",
            "name": "Bianca Tran",
            "pay_type": "hourly",
            "rate": "30.00",
            "hours_worked": "50",
            "pretax_deductions": "50.00",
            "posttax_deductions": "25.00",
        }
        record = logic.calculate_pay(employee, self.config)
        self.assertEqual(record["gross_pay"], D("1590.00"))
        self.assertEqual(record["overtime_pay"], D("270.00"))
        self.assertEqual(record["cpp"], D("86.60"))
        self.assertEqual(record["ei"], D("26.39"))
        self.assertEqual(record["income_tax"], D("308.00"))
        self.assertEqual(record["total_deductions"], D("495.99"))
        self.assertEqual(record["net_pay"], D("1094.01"))

    def test_net_reconciles_with_total_deductions(self):
        employee = {
            "employee_id": "E001",
            "name": "Avery Singh",
            "pay_type": "salaried",
            "rate": "2500.00",
            "hours_worked": "0",
            "pretax_deductions": "100.00",
            "posttax_deductions": "0.00",
        }
        record = logic.calculate_pay(employee, self.config)
        self.assertEqual(
            record["net_pay"],
            record["gross_pay"] - record["total_deductions"],
        )


class RoundingTests(unittest.TestCase):
    def test_round_half_up(self):
        self.assertEqual(logic.money("1.005"), D("1.01"))
        self.assertEqual(logic.money("2.345"), D("2.35"))


class ValidationTests(unittest.TestCase):
    def _row(self, **overrides):
        row = {
            "employee_id": "E100",
            "name": "Test Person",
            "pay_type": "hourly",
            "rate": "20.00",
            "hours_worked": "40",
            "pretax_deductions": "0.00",
            "posttax_deductions": "0.00",
        }
        row.update(overrides)
        return row

    def test_clean_row_has_no_errors(self):
        self.assertEqual(validation.validate_row(self._row()), [])

    def test_missing_value_is_flagged(self):
        errors = validation.validate_row(self._row(rate=""))
        self.assertTrue(any("rate" in error for error in errors))

    def test_unknown_pay_type_is_flagged(self):
        errors = validation.validate_row(self._row(pay_type="contractor"))
        self.assertTrue(any("pay_type" in error for error in errors))

    def test_negative_number_is_flagged(self):
        errors = validation.validate_row(self._row(hours_worked="-5"))
        self.assertTrue(any("hours_worked" in error for error in errors))

    def test_extra_field_is_flagged(self):
        errors = validation.validate_row(self._row(**{validation.EXTRA_FIELD_KEY: ["junk"]}))
        self.assertTrue(any("more fields" in error for error in errors))

    def test_header_missing_column(self):
        header = ["employee_id", "name", "pay_type", "rate", "hours_worked", "pretax_deductions"]
        errors = validation.validate_header(header)
        self.assertTrue(any("posttax_deductions" in error for error in errors))

    def test_header_extra_column(self):
        header = validation.REQUIRED_FIELDS + ["surprise"]
        errors = validation.validate_header(header)
        self.assertTrue(any("surprise" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
