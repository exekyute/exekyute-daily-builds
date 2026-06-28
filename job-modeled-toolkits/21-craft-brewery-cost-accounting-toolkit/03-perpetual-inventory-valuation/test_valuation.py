"""Unit tests for the perpetual inventory valuation tool.

Run from this folder:
    python -m unittest -v
"""

import unittest
from decimal import Decimal

from valuation import (
    issue_cost,
    run_ledger,
    totals_by_category,
    value_inventory,
    weighted_average_unit_cost,
)
from validation import ValidationError, validate


def D(value):
    return Decimal(str(value))


def txn(txn_type, quantity, value="0", sku="RM-MALT", category="raw_material",
        description="malt", unit="kg"):
    return {"txn_type": txn_type, "quantity": D(quantity), "value": D(value),
            "sku": sku, "category": category, "description": description, "unit": unit}


class IssueCostTests(unittest.TestCase):
    def test_issue_at_weighted_average(self):
        # 4500 value over 3000 qty = 1.50/unit; issue 1000 = 1500.00
        self.assertEqual(issue_cost(D("3000"), D("4500"), D("1000")), D("1500.00"))

    def test_issue_from_empty_is_zero(self):
        self.assertEqual(issue_cost(D("0"), D("0"), D("10")), D("0.00"))


class WacTests(unittest.TestCase):
    def test_four_places(self):
        self.assertEqual(weighted_average_unit_cost(D("4000"), D("5050.00")), D("1.2625"))

    def test_zero_qty(self):
        self.assertEqual(weighted_average_unit_cost(D("0"), D("0")), D("0.0000"))


class LedgerTests(unittest.TestCase):
    def test_malt_ending_balance(self):
        # opening 500 @ 631.25, receipts 3000 @ 3750, 1000 @ 1300, issue 830.
        txns = [
            txn("opening", "500", "631.25"),
            txn("receipt", "3000", "3750.00"),
            txn("receipt", "1000", "1300.00"),
            txn("issue", "830"),
        ]
        end = run_ledger(txns)
        # value 5681.25 over 4500 qty = 1.2625; issue 830 = 1047.88.
        self.assertEqual(end["wac_unit_cost"], D("1.2625"))
        self.assertEqual(end["on_hand_qty"], D("3670"))
        self.assertEqual(end["on_hand_value"], D("4633.37"))
        self.assertEqual(end["integrity_flag"], "")

    def test_negative_on_hand_flags(self):
        txns = [txn("opening", "5", "20.00"), txn("issue", "7")]
        end = run_ledger(txns)
        self.assertEqual(end["on_hand_qty"], D("-2"))
        self.assertEqual(end["integrity_flag"], "negative on-hand")

    def test_finished_good_single_receipt(self):
        txns = [
            txn("receipt", "3000", "1302.94", sku="FG-LAGER-CAN", category="finished_goods"),
            txn("issue", "2500", sku="FG-LAGER-CAN", category="finished_goods"),
        ]
        end = run_ledger(txns)
        # unit 0.434313...; issue 2500 = 1085.78; ending 500 -> 217.16
        self.assertEqual(end["on_hand_qty"], D("500"))
        self.assertEqual(end["on_hand_value"], D("217.16"))


class AggregateTests(unittest.TestCase):
    def test_value_inventory_groups_by_sku(self):
        txns = [
            txn("opening", "500", "631.25"),
            txn("receipt", "3000", "3750.00", sku="RM-MALT"),
            txn("receipt", "200", "3936.00", sku="RM-HOPS", description="hops"),
        ]
        rows = value_inventory(txns)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["sku"], "RM-MALT")

    def test_totals_by_category(self):
        rows = [
            {"category": "raw_material", "inventory_value": D("100.00")},
            {"category": "raw_material", "inventory_value": D("50.00")},
            {"category": "finished_goods", "inventory_value": D("200.00")},
        ]
        by_cat, grand = totals_by_category(rows)
        self.assertEqual(by_cat["raw_material"], D("150.00"))
        self.assertEqual(grand, D("350.00"))


class ValidationTests(unittest.TestCase):
    header = list(__import__("validation").REQUIRED_COLUMNS)

    def row(self, **kw):
        base = {"txn_id": "T1", "date": "2026-05-01", "sku": "RM-MALT", "description": "malt",
                "category": "raw_material", "txn_type": "receipt", "quantity": "10",
                "unit": "kg", "value": "12.00"}
        base.update(kw)
        return base

    def test_clean_passes(self):
        validate([self.row()], self.header)

    def test_duplicate_id(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(), self.row()], self.header)
        self.assertTrue(any("duplicate" in p for p in ctx.exception.problems))

    def test_bad_category(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(category="supplies")], self.header)
        self.assertTrue(any("category" in p for p in ctx.exception.problems))

    def test_bad_txn_type(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(txn_type="transfer")], self.header)
        self.assertTrue(any("txn_type" in p for p in ctx.exception.problems))

    def test_negative_quantity(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(quantity="-5")], self.header)
        self.assertTrue(any("greater than zero" in p for p in ctx.exception.problems))

    def test_negative_value(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(value="-5")], self.header)
        self.assertTrue(any("value cannot be negative" in p for p in ctx.exception.problems))

    def test_receipt_missing_value(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(value="")], self.header)
        self.assertTrue(any("needs a value" in p for p in ctx.exception.problems))


if __name__ == "__main__":
    unittest.main()
