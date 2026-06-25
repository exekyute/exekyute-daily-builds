"""Unit tests for the security deposit reconciliation tool.

Run from inside this folder:

    python -m unittest -v

The tests cover the money math in deposit_logic.py and the header and row checks in
deposit_validation.py, using small fixed numbers worked out by hand. The three
settlement outcomes (a refund, a balance owed, and an even result) are each checked.
"""

import unittest
from datetime import date
from decimal import Decimal

import deposit_logic as logic
import deposit_validation as validation


class TestSettlement(unittest.TestCase):
    def test_total_deductions(self):
        self.assertEqual(
            logic.total_deductions(Decimal("1500.00"), Decimal("300.00"), Decimal("500.00")),
            Decimal("2300.00"),
        )

    def test_full_refund_no_deductions(self):
        refund, balance, result = logic.settle(Decimal("1500.00"), Decimal("0.00"))
        self.assertEqual(refund, Decimal("1500.00"))
        self.assertEqual(balance, Decimal("0.00"))
        self.assertEqual(result, logic.RESULT_REFUND)

    def test_partial_refund(self):
        refund, balance, result = logic.settle(Decimal("1800.00"), Decimal("400.00"))
        self.assertEqual(refund, Decimal("1400.00"))
        self.assertEqual(balance, Decimal("0.00"))
        self.assertEqual(result, logic.RESULT_REFUND)

    def test_balance_owed_when_deductions_exceed_deposit(self):
        refund, balance, result = logic.settle(Decimal("2000.00"), Decimal("2300.00"))
        self.assertEqual(refund, Decimal("0.00"))
        self.assertEqual(balance, Decimal("300.00"))
        self.assertEqual(result, logic.RESULT_BALANCE)

    def test_even_when_deductions_equal_deposit(self):
        refund, balance, result = logic.settle(Decimal("1650.00"), Decimal("1650.00"))
        self.assertEqual(refund, Decimal("0.00"))
        self.assertEqual(balance, Decimal("0.00"))
        self.assertEqual(result, logic.RESULT_EVEN)


class TestValidation(unittest.TestCase):
    def setUp(self):
        self.header = list(validation.REQUIRED_COLUMNS)

    def test_missing_column(self):
        bad = ["unit", "tenant", "move_out_date", "unpaid_rent", "cleaning", "damages"]
        with self.assertRaises(validation.ValidationError) as caught:
            validation.check_header(bad)
        self.assertIn("deposit_held", str(caught.exception))

    def test_good_rows(self):
        rows = [
            ["101", "Ava Bennett", "2026-05-31", "1500.00", "0.00", "0.00", "0.00"],
            ["104", "Noah Diaz", "2026-06-12", "2000.00", "1500.00", "300.00", "500.00"],
        ]
        move_outs, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(len(move_outs), 2)
        self.assertEqual(issues, [])
        self.assertEqual(move_outs[0].deposit_held, Decimal("1500.00"))
        self.assertEqual(move_outs[1].damages, Decimal("500.00"))

    def test_blank_deductions_read_as_zero(self):
        rows = [["105", "Priya Kaur", "2026-06-01", "1400.00", "", "", ""]]
        move_outs, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(issues, [])
        self.assertEqual(move_outs[0].unpaid_rent, Decimal("0"))
        self.assertEqual(move_outs[0].cleaning, Decimal("0"))
        self.assertEqual(move_outs[0].damages, Decimal("0"))

    def test_duplicate_unit_skipped(self):
        rows = [
            ["101", "Ava", "2026-05-31", "1500.00", "0.00", "0.00", "0.00"],
            ["101", "Dup", "2026-06-01", "1000.00", "0.00", "0.00", "0.00"],
        ]
        move_outs, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(len(move_outs), 1)
        self.assertIn("duplicate unit", issues[0].reason)

    def test_short_and_extra_skipped(self):
        rows = [
            ["113", "Short", "2026-06-01", "1000.00", "0.00", "0.00"],
            ["114", "Extra", "2026-06-01", "1000.00", "0.00", "0.00", "0.00", "EXTRA"],
        ]
        move_outs, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(move_outs, [])
        self.assertEqual(len(issues), 2)

    def test_bad_money_and_date_skipped(self):
        rows = [
            ["115", "Bad Money", "2026-06-01", "oops", "0.00", "0.00", "0.00"],
            ["116", "Bad Date", "06/01/2026", "1000.00", "0.00", "0.00", "0.00"],
        ]
        move_outs, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(move_outs, [])
        self.assertIn("deposit_held is not a number", issues[0].reason)
        self.assertIn("move_out_date is not in YYYY-MM-DD form", issues[1].reason)


if __name__ == "__main__":
    unittest.main()
