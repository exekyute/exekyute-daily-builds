"""Unit tests for the rent roll calculator.

Run from inside this folder:

    python -m unittest -v

The tests cover the pure money and date math in rent_roll_logic.py and the
header and row checks in rent_roll_validation.py, using small fixed inputs worked
out by hand. The headline case is Unit 101: a 1500.00 monthly rent with a
move-in on 2026-06-16 prorates to exactly 750.00 for June 2026, the same figure
the companion dashboard is checked against.
"""

import unittest
from datetime import date
from decimal import Decimal

import rent_roll_logic as logic
import rent_roll_validation as validation


class TestProration(unittest.TestCase):
    def test_days_in_month_actual(self):
        self.assertEqual(logic.days_in_month(2026, 6), 30)
        self.assertEqual(logic.days_in_month(2026, 2), 28)
        self.assertEqual(logic.days_in_month(2024, 2), 29)
        self.assertEqual(logic.days_in_month(2026, 7), 31)

    def test_full_month_when_no_move_dates(self):
        occupied = logic.occupied_days(2026, 6, None, None)
        self.assertEqual(occupied, 30)
        self.assertEqual(
            logic.prorate_rent(Decimal("1800.00"), occupied, 30), Decimal("1800.00")
        )

    def test_partial_move_in_unit_101(self):
        # Move-in on the 16th of a 30-day month: the 16th through the 30th is 15 days.
        occupied = logic.occupied_days(2026, 6, date(2026, 6, 16), None)
        self.assertEqual(occupied, 15)
        self.assertEqual(
            logic.prorate_rent(Decimal("1500.00"), occupied, 30), Decimal("750.00")
        )

    def test_partial_move_out(self):
        # Move-out on the 10th: the 1st through the 10th is 10 days.
        occupied = logic.occupied_days(2026, 6, None, date(2026, 6, 10))
        self.assertEqual(occupied, 10)
        self.assertEqual(
            logic.prorate_rent(Decimal("1650.00"), occupied, 30), Decimal("550.00")
        )

    def test_boundary_move_in_on_first_is_full_month(self):
        occupied = logic.occupied_days(2026, 6, date(2026, 6, 1), None)
        self.assertEqual(occupied, 30)
        self.assertEqual(
            logic.prorate_rent(Decimal("1400.00"), occupied, 30), Decimal("1400.00")
        )

    def test_boundary_move_out_on_last_is_full_month(self):
        occupied = logic.occupied_days(2026, 6, None, date(2026, 6, 30))
        self.assertEqual(occupied, 30)

    def test_lease_not_active_in_month_is_zero(self):
        # Moved out before the month starts.
        self.assertEqual(logic.occupied_days(2026, 6, None, date(2026, 5, 20)), 0)
        # Moved in after the month ends.
        self.assertEqual(logic.occupied_days(2026, 6, date(2026, 7, 5), None), 0)
        self.assertEqual(logic.prorate_rent(Decimal("1500.00"), 0, 30), Decimal("0.00"))

    def test_rounding_is_half_up(self):
        # 1000 / 30 * 1 day = 33.333..., rounds to 33.33.
        self.assertEqual(logic.prorate_rent(Decimal("1000.00"), 1, 30), Decimal("33.33"))
        # 1000 / 30 * 17 days = 566.666..., rounds half up to 566.67.
        self.assertEqual(logic.prorate_rent(Decimal("1000.00"), 17, 30), Decimal("566.67"))


class TestLateFeeAndDue(unittest.TestCase):
    def test_late_fee_on_overdue(self):
        self.assertEqual(logic.late_fee(Decimal("500.00"), Decimal("0.05")), Decimal("25.00"))

    def test_no_late_fee_when_nothing_overdue(self):
        self.assertEqual(logic.late_fee(Decimal("0"), Decimal("0.05")), Decimal("0.00"))

    def test_amount_due_sums_parts(self):
        due = logic.amount_due(Decimal("2000.00"), Decimal("500.00"), Decimal("25.00"))
        self.assertEqual(due, Decimal("2525.00"))


class TestHeaderValidation(unittest.TestCase):
    def test_missing_column_is_rejected(self):
        header = ["unit", "tenant", "monthly_rent", "move_in", "move_out", "overdue_balance"]
        with self.assertRaises(validation.ValidationError) as caught:
            validation.check_header(header)
        self.assertIn("lease_end", str(caught.exception))

    def test_full_header_passes(self):
        header = list(validation.REQUIRED_COLUMNS)
        # Should not raise.
        validation.check_header(header)


class TestRowValidation(unittest.TestCase):
    def setUp(self):
        self.header = list(validation.REQUIRED_COLUMNS)

    def test_good_rows_become_leases(self):
        rows = [
            ["101", "Ava Bennett", "1500.00", "2026-06-16", "", "2027-05-31", "0.00"],
            ["102", "Liam Carter", "1800.00", "", "", "2026-12-31", ""],
        ]
        leases, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(len(leases), 2)
        self.assertEqual(issues, [])
        self.assertEqual(leases[0].monthly_rent, Decimal("1500.00"))
        self.assertEqual(leases[0].move_in, date(2026, 6, 16))
        self.assertEqual(leases[1].overdue_balance, Decimal("0"))

    def test_short_row_is_skipped(self):
        rows = [["107", "Olivia Frost", "1900.00", "", "", "2026-10-31"]]
        leases, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(leases, [])
        self.assertEqual(len(issues), 1)
        self.assertIn("expected 7 fields", issues[0].reason)

    def test_extra_field_row_is_skipped(self):
        rows = [["108", "Lucas Reed", "1550.00", "", "", "2026-11-30", "0.00", "EXTRA"]]
        leases, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(leases, [])
        self.assertIn("found 8", issues[0].reason)

    def test_duplicate_unit_is_skipped(self):
        rows = [
            ["101", "Ava Bennett", "1500.00", "", "", "2027-05-31", "0.00"],
            ["101", "Ethan Cole", "1750.00", "", "", "2027-03-31", "0.00"],
        ]
        leases, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(len(leases), 1)
        self.assertIn("duplicate unit", issues[0].reason)

    def test_bad_money_is_skipped(self):
        rows = [["109", "Bad Money", "n/a", "", "", "2026-09-30", "0.00"]]
        leases, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(leases, [])
        self.assertIn("monthly_rent is not a number", issues[0].reason)

    def test_bad_date_is_skipped(self):
        rows = [["110", "Bad Date", "1500.00", "06/01/2026", "", "2026-09-30", "0.00"]]
        leases, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(leases, [])
        self.assertIn("YYYY-MM-DD", issues[0].reason)

    def test_move_out_before_move_in_is_skipped(self):
        rows = [["111", "Backwards", "1500.00", "2026-06-20", "2026-06-10", "2026-09-30", "0.00"]]
        leases, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(leases, [])
        self.assertIn("move_out is before move_in", issues[0].reason)


if __name__ == "__main__":
    unittest.main()
