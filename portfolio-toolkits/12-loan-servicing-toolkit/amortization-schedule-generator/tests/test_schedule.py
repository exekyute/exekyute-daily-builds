"""Unit tests for the amortization generator.

Covered: the level payment formula, the hand-checked six-period schedule, the
final-period reconciliation, a zero-interest loan, a single-period loan, that
every schedule closes at exactly zero, and the validation rules for bad input.
"""

import unittest
from decimal import Decimal

from schedule_logic import level_payment, build_schedule
from schedule_validation import validate_inputs


class LevelPaymentTests(unittest.TestCase):

    def test_standard_loan_payment(self):
        # 1000 at 12% annual (1% monthly) over 6 months rounds to 172.55.
        payment = level_payment("1000.00", "12", 6)
        self.assertEqual(payment, Decimal("172.55"))

    def test_zero_interest_payment_is_even_split(self):
        payment = level_payment("1200.00", "0", 12)
        self.assertEqual(payment, Decimal("100.00"))

    def test_single_period_payment_includes_one_month_interest(self):
        # One period: pay the whole principal plus one month of interest.
        payment = level_payment("500.00", "12", 1)
        self.assertEqual(payment, Decimal("505.00"))


class ScheduleTests(unittest.TestCase):

    def test_hand_checked_six_period_schedule(self):
        rows, summary = build_schedule("1000.00", "12", 6)
        expected = [
            (1, "172.55", "10.00", "162.55", "837.45"),
            (2, "172.55", "8.37", "164.18", "673.27"),
            (3, "172.55", "6.73", "165.82", "507.45"),
            (4, "172.55", "5.07", "167.48", "339.97"),
            (5, "172.55", "3.40", "169.15", "170.82"),
            (6, "172.53", "1.71", "170.82", "0.00"),
        ]
        self.assertEqual(len(rows), 6)
        for row, (period, pay, interest, principal, balance) in zip(rows, expected):
            self.assertEqual(row["period"], period)
            self.assertEqual(row["payment"], Decimal(pay))
            self.assertEqual(row["interest"], Decimal(interest))
            self.assertEqual(row["principal"], Decimal(principal))
            self.assertEqual(row["balance"], Decimal(balance))

        self.assertEqual(summary["total_interest"], Decimal("35.28"))
        self.assertEqual(summary["total_paid"], Decimal("1035.28"))

    def test_final_period_is_reconciled(self):
        # The last payment differs from the level payment to close at zero.
        rows, summary = build_schedule("1000.00", "12", 6)
        self.assertNotEqual(rows[-1]["payment"], summary["level_payment"])
        self.assertEqual(rows[-1]["balance"], Decimal("0.00"))

    def test_zero_interest_schedule_has_no_interest(self):
        rows, summary = build_schedule("1200.00", "0", 12)
        self.assertEqual(summary["total_interest"], Decimal("0.00"))
        for row in rows:
            self.assertEqual(row["interest"], Decimal("0.00"))
        self.assertEqual(rows[-1]["balance"], Decimal("0.00"))

    def test_single_period_schedule_closes_at_zero(self):
        rows, summary = build_schedule("500.00", "12", 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["interest"], Decimal("5.00"))
        self.assertEqual(rows[0]["principal"], Decimal("500.00"))
        self.assertEqual(rows[0]["balance"], Decimal("0.00"))

    def test_balance_always_closes_at_zero(self):
        # A spread of loans should each land on exactly zero.
        cases = [
            ("2500.00", "7.25", 24),
            ("18000.00", "5.9", 60),
            ("333.33", "9.99", 7),
            ("100000.00", "0", 360),
        ]
        for principal, rate, term in cases:
            rows, _ = build_schedule(principal, rate, term)
            self.assertEqual(rows[-1]["balance"], Decimal("0.00"),
                             msg=f"{principal} / {rate} / {term}")

    def test_payments_account_for_principal_plus_interest(self):
        rows, summary = build_schedule("2500.00", "7.25", 24)
        self.assertEqual(
            summary["total_paid"],
            Decimal("2500.00") + summary["total_interest"],
        )


class ValidationTests(unittest.TestCase):

    def test_valid_inputs_have_no_errors(self):
        self.assertEqual(validate_inputs("1000.00", "12", "6"), [])

    def test_zero_rate_is_allowed(self):
        self.assertEqual(validate_inputs("1000.00", "0", "6"), [])

    def test_negative_principal_rejected(self):
        self.assertTrue(validate_inputs("-5", "12", "6"))

    def test_zero_principal_rejected(self):
        self.assertTrue(validate_inputs("0", "12", "6"))

    def test_negative_rate_rejected(self):
        self.assertTrue(validate_inputs("1000", "-5", "6"))

    def test_zero_term_rejected(self):
        self.assertTrue(validate_inputs("1000", "12", "0"))

    def test_non_integer_term_rejected(self):
        self.assertTrue(validate_inputs("1000", "12", "6.5"))

    def test_non_numeric_inputs_rejected(self):
        errors = validate_inputs("abc", "xyz", "soon")
        self.assertEqual(len(errors), 3)


if __name__ == "__main__":
    unittest.main()
