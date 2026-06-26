"""Unit tests for the lease renewal scheduler.

Run from inside this folder:

    python -m unittest -v

The tests cover the date and money math in renewal_logic.py and the header and row
checks in renewal_validation.py, using small fixed dates worked out by hand. The
headline case is Unit 101: a 1500.00 rent escalated by 4 percent is exactly 1560.00,
the figure the companion renewal tracker is checked against.
"""

import unittest
from datetime import date
from decimal import Decimal

import renewal_logic as logic
import renewal_validation as validation


class TestEscalation(unittest.TestCase):
    def test_unit_101_escalation(self):
        self.assertEqual(
            logic.escalate_rent(Decimal("1500.00"), Decimal("0.04")), Decimal("1560.00")
        )

    def test_escalation_rounds_half_up(self):
        # 1333.33 * 1.04 = 1386.6632, rounds to 1386.66.
        self.assertEqual(
            logic.escalate_rent(Decimal("1333.33"), Decimal("0.04")), Decimal("1386.66")
        )

    def test_zero_escalation_keeps_rent(self):
        self.assertEqual(
            logic.escalate_rent(Decimal("1800.00"), Decimal("0")), Decimal("1800.00")
        )


class TestDateMath(unittest.TestCase):
    def test_add_months_simple(self):
        self.assertEqual(logic.add_months(date(2026, 6, 1), 12), date(2027, 6, 1))

    def test_add_months_clamps_short_month(self):
        # January 31 plus one month clamps to February 28 in a non-leap year.
        self.assertEqual(logic.add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        # And to February 29 in a leap year.
        self.assertEqual(logic.add_months(date(2024, 1, 31), 1), date(2024, 2, 29))

    def test_renewal_window_full_year(self):
        start, end = logic.renewal_window(date(2027, 5, 31), 12)
        self.assertEqual(start, date(2027, 6, 1))
        self.assertEqual(end, date(2028, 5, 31))

    def test_renewal_window_mid_month_end(self):
        start, end = logic.renewal_window(date(2026, 8, 11), 12)
        self.assertEqual(start, date(2026, 8, 12))
        self.assertEqual(end, date(2027, 8, 11))

    def test_notice_due_date(self):
        self.assertEqual(
            logic.notice_due_date(date(2027, 5, 31), 90), date(2027, 3, 2)
        )

    def test_days_between_signed(self):
        self.assertEqual(logic.days_between(date(2026, 6, 12), date(2026, 6, 30)), 18)
        self.assertEqual(logic.days_between(date(2026, 6, 12), date(2026, 6, 2)), -10)


class TestStatus(unittest.TestCase):
    def setUp(self):
        self.as_of = date(2026, 6, 12)

    def test_expired_when_lease_ended(self):
        lease_end = date(2026, 5, 31)
        notice = logic.notice_due_date(lease_end, 90)
        self.assertEqual(logic.status_for(lease_end, self.as_of, notice), logic.STATUS_EXPIRED)

    def test_due_now_inside_notice_window(self):
        lease_end = date(2026, 6, 30)
        notice = logic.notice_due_date(lease_end, 90)  # 2026-04-01, already passed
        self.assertEqual(logic.status_for(lease_end, self.as_of, notice), logic.STATUS_DUE_NOW)

    def test_upcoming_before_notice_window(self):
        lease_end = date(2027, 5, 31)
        notice = logic.notice_due_date(lease_end, 90)  # 2027-03-02, in the future
        self.assertEqual(logic.status_for(lease_end, self.as_of, notice), logic.STATUS_UPCOMING)

    def test_due_now_exactly_on_notice_date(self):
        # When the as-of date is exactly the notice date, the notice is due now.
        lease_end = date(2026, 9, 10)
        notice = logic.notice_due_date(lease_end, 90)
        self.assertEqual(notice, date(2026, 6, 12))
        self.assertEqual(logic.status_for(lease_end, notice, notice), logic.STATUS_DUE_NOW)


class TestValidation(unittest.TestCase):
    def setUp(self):
        self.header = ["unit", "tenant", "monthly_rent", "move_in", "move_out", "lease_end", "overdue_balance"]

    def test_missing_required_column(self):
        bad = ["unit", "tenant", "monthly_rent", "move_in", "move_out", "overdue_balance"]
        with self.assertRaises(validation.ValidationError) as caught:
            validation.check_header(bad)
        self.assertIn("lease_end", str(caught.exception))

    def test_extra_columns_are_allowed(self):
        # The full leases header carries columns this tool ignores; it must pass.
        validation.check_header(self.header)

    def test_good_rows_become_leases(self):
        rows = [
            ["101", "Ava Bennett", "1500.00", "2026-06-16", "", "2027-05-31", "0.00"],
            ["102", "Liam Carter", "1800.00", "", "", "2026-12-31", ""],
        ]
        leases, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(len(leases), 2)
        self.assertEqual(issues, [])
        self.assertEqual(leases[0].monthly_rent, Decimal("1500.00"))
        self.assertEqual(leases[0].lease_end, date(2027, 5, 31))

    def test_duplicate_unit_skipped(self):
        rows = [
            ["101", "Ava", "1500.00", "", "", "2027-05-31", "0.00"],
            ["101", "Ethan", "1750.00", "", "", "2027-03-31", "0.00"],
        ]
        leases, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(len(leases), 1)
        self.assertIn("duplicate unit", issues[0].reason)

    def test_short_and_extra_rows_skipped(self):
        rows = [
            ["107", "Olivia", "1900.00", "", "", "2026-10-31"],
            ["108", "Lucas", "1550.00", "", "", "2026-11-30", "0.00", "EXTRA"],
        ]
        leases, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(leases, [])
        self.assertEqual(len(issues), 2)

    def test_missing_lease_end_skipped(self):
        rows = [["110", "No End", "1500.00", "", "", "", "0.00"]]
        leases, issues = validation.validate_rows(self.header, rows)
        self.assertEqual(leases, [])
        self.assertIn("lease_end is required", issues[0].reason)


if __name__ == "__main__":
    unittest.main()
