"""Unit tests for the delinquency and aging ledger.

Run from inside this folder:

    python -m unittest -v

The tests cover the money and date math in aging_logic.py and the header and row
checks in aging_validation.py, using small fixed numbers worked out by hand. The
bucket boundaries (exactly 30 versus 31 days) and the grace period (a few days late
with no fee yet) are checked directly.
"""

import unittest
from datetime import date
from decimal import Decimal

import aging_logic as logic
import aging_validation as validation


class TestBalanceAndOverdue(unittest.TestCase):
    def test_balance(self):
        self.assertEqual(logic.balance(Decimal("1650.00"), Decimal("150.00")), Decimal("1500.00"))

    def test_balance_zero_when_paid(self):
        self.assertEqual(logic.balance(Decimal("1200.00"), Decimal("1200.00")), Decimal("0.00"))

    def test_balance_negative_when_overpaid(self):
        self.assertEqual(logic.balance(Decimal("800.00"), Decimal("900.00")), Decimal("-100.00"))

    def test_days_overdue_past_due(self):
        self.assertEqual(logic.days_overdue(date(2026, 6, 12), date(2026, 5, 13)), 30)

    def test_days_overdue_not_yet_due_is_zero(self):
        self.assertEqual(logic.days_overdue(date(2026, 6, 12), date(2026, 6, 20)), 0)


class TestBuckets(unittest.TestCase):
    def test_current(self):
        self.assertEqual(logic.bucket_for(0), logic.BUCKET_CURRENT)

    def test_boundary_30_is_1_30(self):
        self.assertEqual(logic.bucket_for(30), logic.BUCKET_1_30)

    def test_boundary_31_is_31_60(self):
        self.assertEqual(logic.bucket_for(31), logic.BUCKET_31_60)

    def test_boundary_60_and_61(self):
        self.assertEqual(logic.bucket_for(60), logic.BUCKET_31_60)
        self.assertEqual(logic.bucket_for(61), logic.BUCKET_61_90)

    def test_boundary_90_and_91(self):
        self.assertEqual(logic.bucket_for(90), logic.BUCKET_61_90)
        self.assertEqual(logic.bucket_for(91), logic.BUCKET_90_PLUS)


class TestLateFee(unittest.TestCase):
    def test_no_fee_within_grace(self):
        # Three days late, grace of five days: no fee yet.
        self.assertEqual(
            logic.late_fee(Decimal("1800.00"), 3, 5, Decimal("0.05")), Decimal("0.00")
        )

    def test_fee_past_grace(self):
        self.assertEqual(
            logic.late_fee(Decimal("2000.00"), 31, 5, Decimal("0.05")), Decimal("100.00")
        )

    def test_no_fee_when_nothing_owed(self):
        self.assertEqual(
            logic.late_fee(Decimal("0.00"), 60, 5, Decimal("0.05")), Decimal("0.00")
        )

    def test_total_owed(self):
        self.assertEqual(
            logic.total_owed(Decimal("1750.00"), Decimal("87.50")), Decimal("1837.50")
        )


class TestValidation(unittest.TestCase):
    def setUp(self):
        self.header = list(validation.REQUIRED_COLUMNS)

    def test_missing_column(self):
        bad = ["unit", "tenant", "charge_type", "amount_charged", "amount_paid"]
        with self.assertRaises(validation.ValidationError) as caught:
            validation.check_header(bad)
        self.assertIn("due_date", str(caught.exception))

    def test_good_rows(self):
        rows = [
            ["103", "Maya Singh", "Rent", "2026-05-13", "1650.00", "150.00"],
            ["108", "Henry Vale", "Rent", "2026-05-01", "1200.00", "1200.00"],
        ]
        charges, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(len(charges), 2)
        self.assertEqual(issues, [])
        self.assertEqual(charges[0].amount_charged, Decimal("1650.00"))
        self.assertEqual(charges[0].due_date, date(2026, 5, 13))

    def test_duplicate_unit_skipped(self):
        rows = [
            ["101", "Ava", "Rent", "2026-06-20", "1500.00", "0.00"],
            ["101", "Dup", "Rent", "2026-05-01", "1000.00", "0.00"],
        ]
        charges, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(len(charges), 1)
        self.assertIn("duplicate unit", issues[0].reason)

    def test_short_and_extra_skipped(self):
        rows = [
            ["113", "Short", "Rent", "2026-05-01", "1000.00"],
            ["114", "Extra", "Rent", "2026-05-01", "1000.00", "0.00", "EXTRA"],
        ]
        charges, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(charges, [])
        self.assertEqual(len(issues), 2)

    def test_bad_money_and_date_skipped(self):
        rows = [
            ["115", "Bad Money", "Rent", "2026-05-01", "oops", "0.00"],
            ["116", "Bad Date", "Rent", "05/01/2026", "1000.00", "0.00"],
        ]
        charges, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(charges, [])
        self.assertIn("amount_charged is not a number", issues[0].reason)
        self.assertIn("due_date is not in YYYY-MM-DD form", issues[1].reason)


if __name__ == "__main__":
    unittest.main()
