"""Unit tests for the Multi-Currency Consultant Ledger logic and validation."""

import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ledger import convert_to_base, process_invoices  # noqa: E402
from validators import (  # noqa: E402
    InvalidInvoice,
    validate_amount,
    validate_currency,
    validate_invoice_id,
)


def row(invoice_id, currency, amount, consultant="Test Consultant"):
    return {
        "invoice_id": invoice_id,
        "consultant": consultant,
        "currency": currency,
        "amount": amount,
    }


class ConversionTests(unittest.TestCase):
    def test_usd_is_unchanged(self):
        self.assertEqual(convert_to_base(Decimal("45000.00"), "USD"),
                         Decimal("45000.00"))

    def test_eur_conversion(self):
        self.assertEqual(convert_to_base(Decimal("60000.00"), "EUR"),
                         Decimal("64800.00"))

    def test_jpy_conversion(self):
        self.assertEqual(convert_to_base(Decimal("9000000"), "JPY"),
                         Decimal("60300.00"))

    def test_rounding_is_half_up_two_places(self):
        # 100.005 * 1.08 = 108.0054 -> 108.01 with ROUND_HALF_UP at 2 places.
        self.assertEqual(convert_to_base(Decimal("100.005"), "EUR"),
                         Decimal("108.01"))


class ValidationTests(unittest.TestCase):
    def test_blank_invoice_id_rejected(self):
        with self.assertRaises(InvalidInvoice):
            validate_invoice_id("   ")

    def test_unknown_currency_rejected(self):
        with self.assertRaises(InvalidInvoice):
            validate_currency("XYZ")

    def test_currency_is_uppercased(self):
        self.assertEqual(validate_currency("eur"), "EUR")

    def test_non_numeric_amount_rejected(self):
        with self.assertRaises(InvalidInvoice):
            validate_amount("not-a-number")

    def test_blank_amount_rejected(self):
        with self.assertRaises(InvalidInvoice):
            validate_amount("")

    def test_non_positive_amount_rejected(self):
        with self.assertRaises(InvalidInvoice):
            validate_amount("0")


class ProcessInvoicesTests(unittest.TestCase):
    def test_seeded_batch_totals(self):
        records = [
            row("INV-001", "USD", "45000.00"),
            row("INV-002", "EUR", "60000.00"),
            row("INV-003", "GBP", "50000.00"),
            row("INV-004", "JPY", "9000000"),
            row("INV-005", "USD", "15000.00"),
            row("INV-006", "XYZ", "5000.00"),
            row("INV-003", "GBP", "99999.00"),
            row("INV-007", "USD", ""),
            row("INV-008", "EUR", "not-a-number"),
        ]
        result = process_invoices(records, "250000.00")

        self.assertEqual(result.invoice_count, 5)
        self.assertEqual(result.consultant_spend, Decimal("248600.00"))
        self.assertEqual(result.remaining, Decimal("1400.00"))
        self.assertFalse(result.over_budget)
        self.assertEqual(len(result.skipped), 3)   # XYZ, blank amount, non-numeric
        self.assertEqual(len(result.duplicates), 1)  # repeated INV-003

    def test_duplicate_keeps_first_occurrence(self):
        records = [
            row("INV-001", "USD", "100.00"),
            row("INV-001", "USD", "999.00"),
        ]
        result = process_invoices(records, "250000.00")
        self.assertEqual(result.invoice_count, 1)
        self.assertEqual(result.consultant_spend, Decimal("100.00"))

    def test_over_budget_boundary(self):
        records = [row("INV-001", "USD", "250000.01")]
        result = process_invoices(records, "250000.00")
        self.assertTrue(result.over_budget)
        self.assertEqual(result.remaining, Decimal("-0.01"))

    def test_exact_grant_is_not_over_budget(self):
        records = [row("INV-001", "USD", "250000.00")]
        result = process_invoices(records, "250000.00")
        self.assertFalse(result.over_budget)
        self.assertEqual(result.remaining, Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
