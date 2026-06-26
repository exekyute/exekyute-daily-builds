"""Unit tests for the AR Aging and Late-Fee Engine.

Run from this folder with:
    python -m unittest -v
"""

import unittest
from datetime import date
from decimal import Decimal

import aging
import validation

RATE = Decimal("0.015")
REFERENCE = date(2026, 6, 12)


class DaysPastDueTests(unittest.TestCase):
    def test_future_due_date_is_not_overdue(self):
        self.assertEqual(aging.days_past_due(date(2026, 7, 15), REFERENCE), -33)

    def test_due_today_is_zero(self):
        self.assertEqual(aging.days_past_due(date(2026, 6, 12), REFERENCE), 0)

    def test_overdue_is_positive(self):
        self.assertEqual(aging.days_past_due(date(2026, 3, 14), REFERENCE), 90)


class BucketBoundaryTests(unittest.TestCase):
    def test_current_includes_zero_and_negative(self):
        self.assertEqual(aging.aging_bucket(-5), "Current")
        self.assertEqual(aging.aging_bucket(0), "Current")

    def test_lower_edge_of_first_overdue_bucket(self):
        self.assertEqual(aging.aging_bucket(1), "1-30")

    def test_thirty_stays_in_first_bucket(self):
        self.assertEqual(aging.aging_bucket(30), "1-30")

    def test_thirty_one_moves_up(self):
        self.assertEqual(aging.aging_bucket(31), "31-60")

    def test_sixty_and_sixty_one(self):
        self.assertEqual(aging.aging_bucket(60), "31-60")
        self.assertEqual(aging.aging_bucket(61), "61-90")

    def test_ninety_stays_then_ninety_one_moves_up(self):
        self.assertEqual(aging.aging_bucket(90), "61-90")
        self.assertEqual(aging.aging_bucket(91), "90-plus")


class LateFeeTests(unittest.TestCase):
    def test_current_invoice_has_no_fee(self):
        self.assertEqual(aging.late_fee(Decimal("500.00"), -33, RATE), Decimal("0.00"))
        self.assertEqual(aging.late_fee(Decimal("500.00"), 0, RATE), Decimal("0.00"))

    def test_simple_fee(self):
        self.assertEqual(aging.late_fee(Decimal("1000.00"), 90, RATE), Decimal("15.00"))

    def test_round_half_up(self):
        # 123.00 * 0.015 = 1.845 -> rounds up to 1.85
        self.assertEqual(aging.late_fee(Decimal("123.00"), 15, RATE), Decimal("1.85"))

    def test_round_half_up_tiny(self):
        # 1.00 * 0.015 = 0.015 -> rounds up to 0.02
        self.assertEqual(aging.late_fee(Decimal("1.00"), 5, RATE), Decimal("0.02"))


class AgeInvoiceTests(unittest.TestCase):
    def test_hand_checked_invoice(self):
        invoice = aging.Invoice(
            invoice_number="INV-1004",
            customer="Umbrella Supply",
            issue_date=date(2026, 2, 12),
            due_date=date(2026, 3, 14),
            amount=Decimal("1000.00"),
        )
        aged = aging.age_invoice(invoice, REFERENCE, RATE)
        self.assertEqual(aged.days_past_due, 90)
        self.assertEqual(aged.aging_bucket, "61-90")
        self.assertEqual(aged.late_fee, Decimal("15.00"))
        self.assertEqual(aged.total_due, Decimal("1015.00"))


class SummaryTests(unittest.TestCase):
    def setUp(self):
        invoices = [
            aging.Invoice("A", "Cust A", date(2026, 6, 1), date(2026, 7, 1), Decimal("500.00")),
            aging.Invoice("B", "Cust B", date(2026, 4, 28), date(2026, 5, 28), Decimal("123.00")),
            aging.Invoice("C", "Cust C", date(2026, 4, 13), date(2026, 5, 13), Decimal("800.00")),
        ]
        self.aged = aging.age_invoices(invoices, REFERENCE, RATE)

    def test_counts_and_totals_per_bucket(self):
        summary = aging.summarize(self.aged)
        self.assertEqual(summary["Current"]["count"], 1)
        self.assertEqual(summary["Current"]["total"], Decimal("500.00"))
        self.assertEqual(summary["1-30"]["count"], 2)
        self.assertEqual(summary["1-30"]["total"], Decimal("936.85"))
        self.assertEqual(summary["31-60"]["count"], 0)

    def test_grand_total(self):
        self.assertEqual(aging.grand_total(self.aged), Decimal("1436.85"))


class MoneyFormatTests(unittest.TestCase):
    def test_two_decimals_and_no_scientific_notation(self):
        self.assertEqual(aging.money(Decimal("2000")), "2000.00")
        self.assertEqual(aging.money(Decimal("0")), "0.00")
        self.assertEqual(aging.money(Decimal("1015.0")), "1015.00")


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.seen = set()

    def good_row(self):
        return ["INV-9001", "Test Co", "2026-04-01", "2026-05-01", "100.00"]

    def test_accepts_a_clean_row(self):
        invoice = validation.validate_row(self.good_row(), self.seen)
        self.assertEqual(invoice.invoice_number, "INV-9001")
        self.assertEqual(invoice.amount, Decimal("100.00"))

    def test_rejects_missing_field(self):
        with self.assertRaises(validation.RowError):
            validation.validate_row(self.good_row()[:4], self.seen)

    def test_rejects_extra_field(self):
        with self.assertRaises(validation.RowError):
            validation.validate_row(self.good_row() + ["extra"], self.seen)

    def test_rejects_duplicate_invoice_number(self):
        validation.validate_row(self.good_row(), self.seen)
        with self.assertRaises(validation.RowError):
            validation.validate_row(self.good_row(), self.seen)

    def test_rejects_zero_amount(self):
        row = self.good_row()
        row[4] = "0.00"
        with self.assertRaises(validation.RowError):
            validation.validate_row(row, self.seen)

    def test_rejects_negative_amount(self):
        row = self.good_row()
        row[4] = "-50.00"
        with self.assertRaises(validation.RowError):
            validation.validate_row(row, self.seen)

    def test_rejects_non_numeric_amount(self):
        row = self.good_row()
        row[4] = "abc"
        with self.assertRaises(validation.RowError):
            validation.validate_row(row, self.seen)

    def test_rejects_bad_date(self):
        row = self.good_row()
        row[2] = "2026-13-01"
        with self.assertRaises(validation.RowError):
            validation.validate_row(row, self.seen)

    def test_rejects_due_before_issue(self):
        row = self.good_row()
        row[2] = "2026-05-01"
        row[3] = "2026-04-01"
        with self.assertRaises(validation.RowError):
            validation.validate_row(row, self.seen)

    def test_rejects_missing_invoice_number(self):
        row = self.good_row()
        row[0] = ""
        with self.assertRaises(validation.RowError):
            validation.validate_row(row, self.seen)

    def test_validate_header_accepts_expected(self):
        validation.validate_header(list(validation.INPUT_HEADER))

    def test_validate_header_rejects_wrong_columns(self):
        with self.assertRaises(validation.RowError):
            validation.validate_header(["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
