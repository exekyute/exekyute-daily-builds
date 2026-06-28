"""Unit tests for the procurement landed-cost engine.

Run from this folder:
    python -m unittest -v
"""

import unittest
from decimal import Decimal

from landed import (
    allocate_freight,
    cost_all,
    cost_purchase_order,
    duty_amount,
    extended_value,
    landed_unit_cost,
)
from validation import ValidationError, validate


def D(value):
    return Decimal(str(value))


class FreightAllocationTests(unittest.TestCase):
    def test_allocates_by_value_and_sums_to_total(self):
        shares = allocate_freight([D("4500.00"), D("800.00")], D("90.00"))
        self.assertEqual(sum(shares), D("90.00"))
        # 90 * 4500/5300 = 76.415..., 90 * 800/5300 = 13.584...
        self.assertEqual(shares[0], D("76.42"))
        self.assertEqual(shares[1], D("13.58"))

    def test_equal_values_split_evenly(self):
        shares = allocate_freight([D("3600.00"), D("3600.00")], D("300.00"))
        self.assertEqual(shares, [D("150.00"), D("150.00")])

    def test_zero_freight(self):
        self.assertEqual(allocate_freight([D("100"), D("200")], D("0")), [D("0.00"), D("0.00")])

    def test_zero_total_value_spreads_evenly(self):
        shares = allocate_freight([D("0"), D("0")], D("10.00"))
        self.assertEqual(sum(shares), D("10.00"))

    def test_single_line_takes_all(self):
        self.assertEqual(allocate_freight([D("3600.00")], D("120.00")), [D("120.00")])


class LineMathTests(unittest.TestCase):
    def test_extended_value(self):
        self.assertEqual(extended_value(D("200"), D("18.00")), D("3600.00"))

    def test_duty_amount(self):
        self.assertEqual(duty_amount(D("3600.00"), D("6.0")), D("216.00"))

    def test_duty_zero_when_domestic(self):
        self.assertEqual(duty_amount(D("3600.00"), D("0")), D("0.00"))

    def test_landed_unit_cost_four_places(self):
        self.assertEqual(landed_unit_cost(D("3750.00"), D("40000")), D("0.0938"))

    def test_landed_unit_cost_zero_quantity(self):
        self.assertEqual(landed_unit_cost(D("0"), D("0")), D("0.0000"))


class PurchaseOrderTests(unittest.TestCase):
    def line(self, **kw):
        base = {
            "po_id": "PO-1",
            "line_id": "1",
            "sku": "RM-X",
            "description": "x",
            "category": "raw_material",
            "quantity": D("1"),
            "unit": "kg",
            "unit_price": D("1"),
            "freight_total": D("0"),
            "duty_rate": D("0"),
        }
        base.update(kw)
        return base

    def test_imported_hops_landed_unit_cost(self):
        # 200 kg at 18.00 = 3600 extended; freight 120 all to the one line;
        # duty 6% of 3600 = 216; landed 3936; unit 19.68.
        line = self.line(sku="RM-HOPS", quantity=D("200"), unit_price=D("18.00"),
                         freight_total=D("120.00"), duty_rate=D("6.0"))
        result = cost_purchase_order([line])[0]
        self.assertEqual(result["extended_value"], D("3600.00"))
        self.assertEqual(result["freight_alloc"], D("120.00"))
        self.assertEqual(result["duty"], D("216.00"))
        self.assertEqual(result["landed_total"], D("3936.00"))
        self.assertEqual(result["landed_unit_cost"], D("19.6800"))

    def test_two_line_po_freight_split(self):
        lines = [
            self.line(line_id="1", sku="RM-MALT", quantity=D("3000"), unit_price=D("1.20"),
                      freight_total=D("300.00")),
            self.line(line_id="2", sku="PKG-CAN-355", category="packaging_material",
                      quantity=D("40000"), unit_price=D("0.09"), freight_total=D("300.00")),
        ]
        results = cost_purchase_order(lines)
        self.assertEqual(results[0]["freight_alloc"], D("150.00"))
        self.assertEqual(results[1]["freight_alloc"], D("150.00"))
        self.assertEqual(results[0]["landed_total"], D("3750.00"))
        self.assertEqual(results[1]["landed_total"], D("3750.00"))

    def test_cost_all_groups_by_po(self):
        lines = [
            self.line(po_id="PO-A", line_id="1"),
            self.line(po_id="PO-B", line_id="1"),
            self.line(po_id="PO-A", line_id="2"),
        ]
        results = cost_all(lines)
        self.assertEqual(len(results), 3)
        self.assertEqual([r["po_id"] for r in results], ["PO-A", "PO-A", "PO-B"])


class ValidationTests(unittest.TestCase):
    header = list(__import__("validation").REQUIRED_COLUMNS)

    def row(self, **kw):
        base = {
            "po_id": "PO-1", "line_id": "1", "date": "2026-05-01", "sku": "RM-X",
            "description": "x", "category": "raw_material", "quantity": "10",
            "unit": "kg", "unit_price": "1.00", "freight_total": "0", "duty_rate": "0",
        }
        base.update(kw)
        return base

    def test_clean_rows_pass(self):
        validate([self.row()], self.header)  # no raise

    def test_missing_column(self):
        with self.assertRaises(ValidationError):
            validate([{"po_id": "PO-1"}], ["po_id"])

    def test_duplicate_key(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(), self.row()], self.header)
        self.assertTrue(any("duplicate" in p for p in ctx.exception.problems))

    def test_negative_quantity(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(quantity="-5")], self.header)
        self.assertTrue(any("greater than zero" in p for p in ctx.exception.problems))

    def test_bad_category(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(category="supplies")], self.header)
        self.assertTrue(any("category" in p for p in ctx.exception.problems))

    def test_non_numeric_price(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(unit_price="abc")], self.header)
        self.assertTrue(any("unit_price" in p for p in ctx.exception.problems))

    def test_negative_freight(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(freight_total="-50")], self.header)
        self.assertTrue(any("freight_total" in p for p in ctx.exception.problems))

    def test_freight_mismatch_within_po(self):
        rows = [
            self.row(line_id="1", freight_total="200.00"),
            self.row(line_id="2", freight_total="150.00"),
        ]
        with self.assertRaises(ValidationError) as ctx:
            validate(rows, self.header)
        self.assertTrue(any("disagrees" in p for p in ctx.exception.problems))


if __name__ == "__main__":
    unittest.main()
