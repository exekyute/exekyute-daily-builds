"""Unit tests for the Freight Cost Allocator pure logic.

Run from this folder with:

    python -m unittest -v

The tests cover the allocation math (exact reconciliation, the largest-remainder
tie-break, zero-basis lines), the money formatting, and every validation rule.
"""

import unittest
from decimal import Decimal

import allocator_logic as logic


def make_item(line_id, quantity, unit_cost, weight, description="line"):
    return logic.LineItem(
        line_id=line_id,
        description=description,
        quantity=quantity,
        unit_cost=Decimal(unit_cost),
        weight=Decimal(weight),
    )


class FormatCentsTests(unittest.TestCase):
    def test_fixed_point_two_places(self):
        self.assertEqual(logic.format_cents(2593), "25.93")
        self.assertEqual(logic.format_cents(0), "0.00")
        self.assertEqual(logic.format_cents(5), "0.05")
        self.assertEqual(logic.format_cents(10000), "100.00")

    def test_no_scientific_notation_for_large_values(self):
        self.assertEqual(logic.format_cents(123456789), "1234567.89")


class ToCentsTests(unittest.TestCase):
    def test_round_half_up(self):
        self.assertEqual(logic.to_cents(Decimal("0.005")), 1)
        self.assertEqual(logic.to_cents(Decimal("0.004")), 0)
        self.assertEqual(logic.to_cents(Decimal("10.00")), 1000)


class AllocateTests(unittest.TestCase):
    def test_clean_even_split_by_weight(self):
        items = [
            make_item("A", 1, "0", "20"),
            make_item("B", 1, "0", "12"),
            make_item("C", 1, "0", "8"),
            make_item("D", 1, "0", "60"),
        ]
        allocations = logic.allocate(items, 10000, "weight")
        self.assertEqual(allocations, [2000, 1200, 800, 6000])
        self.assertEqual(sum(allocations), 10000)

    def test_uneven_split_reconciles_with_largest_remainder(self):
        # Three equal lines, 100.00 by value. Exact share is 33.33.. each.
        # Flooring loses one cent; it goes to the first line by the tie-break.
        items = [
            make_item("A", 1, "10", "1"),
            make_item("B", 1, "10", "1"),
            make_item("C", 1, "10", "1"),
        ]
        allocations = logic.allocate(items, 10000, "value")
        self.assertEqual(allocations, [3334, 3333, 3333])
        self.assertEqual(sum(allocations), 10000)

    def test_sample_shipment_value_basis_is_exact(self):
        items = self._sample_items()
        allocations = logic.allocate(items, 10000, "value")
        self.assertEqual(allocations, [2593, 2222, 1481, 0, 3704])
        self.assertEqual(sum(allocations), 10000)

    def test_sample_shipment_weight_basis_is_exact(self):
        items = self._sample_items()
        allocations = logic.allocate(items, 10000, "weight")
        self.assertEqual(allocations, [2000, 1200, 0, 800, 6000])
        self.assertEqual(sum(allocations), 10000)

    def test_zero_value_line_gets_nothing_under_value_basis(self):
        items = self._sample_items()
        allocations = logic.allocate(items, 10000, "value")
        # L004 has unit_cost 0, so its value is 0.
        self.assertEqual(allocations[3], 0)

    def test_zero_weight_line_gets_nothing_under_weight_basis(self):
        items = self._sample_items()
        allocations = logic.allocate(items, 10000, "weight")
        # L003 has weight 0.
        self.assertEqual(allocations[2], 0)

    def test_zero_freight_allocates_all_zeros(self):
        items = self._sample_items()
        allocations = logic.allocate(items, 0, "value")
        self.assertEqual(allocations, [0, 0, 0, 0, 0])

    def test_all_zero_basis_total_is_rejected(self):
        items = [make_item("A", 1, "0", "0"), make_item("B", 1, "0", "0")]
        with self.assertRaises(logic.ValidationError):
            logic.allocate(items, 10000, "value")
        with self.assertRaises(logic.ValidationError):
            logic.allocate(items, 10000, "weight")

    def test_invalid_basis_is_rejected(self):
        items = [make_item("A", 1, "10", "5")]
        with self.assertRaises(logic.ValidationError):
            logic.allocate(items, 10000, "volume")

    def test_reconciliation_holds_across_many_freight_amounts(self):
        items = self._sample_items()
        for freight_cents in range(0, 5000, 7):
            allocations = logic.allocate(items, freight_cents, "value")
            self.assertEqual(sum(allocations), freight_cents)

    def _sample_items(self):
        # Mirrors data/sample_shipment.csv.
        return [
            make_item("L001", 7, "5.00", "20.0"),
            make_item("L002", 3, "10.00", "12.0"),
            make_item("L003", 5, "4.00", "0.0"),
            make_item("L004", 2, "0.00", "8.0"),
            make_item("L005", 1, "50.00", "60.0"),
        ]


class LandedRowTests(unittest.TestCase):
    def test_landed_unit_cost_adds_freight_per_unit(self):
        item = make_item("L001", 7, "5.00", "20.0")
        # 25.93 of freight over 7 units is 3.70 per unit, plus 5.00 unit cost.
        self.assertEqual(logic.landed_unit_cost_cents(item, 2593), 870)

    def test_build_landed_rows_shape_and_formatting(self):
        items = [make_item("L005", 1, "50.00", "60.0", "Pallet")]
        header, rows = logic.build_landed_rows(items, [3704])
        self.assertEqual(
            header,
            [
                "line_id",
                "description",
                "quantity",
                "unit_cost",
                "allocated_freight",
                "landed_unit_cost",
            ],
        )
        self.assertEqual(rows[0], ["L005", "Pallet", "1", "50.00", "37.04", "87.04"])


class ParseFreightTests(unittest.TestCase):
    def test_parses_dollars_to_cents(self):
        self.assertEqual(logic.parse_freight_cents("100.00"), 10000)
        self.assertEqual(logic.parse_freight_cents("0"), 0)

    def test_negative_is_rejected(self):
        with self.assertRaises(logic.ValidationError):
            logic.parse_freight_cents("-5.00")

    def test_non_numeric_is_rejected(self):
        with self.assertRaises(logic.ValidationError):
            logic.parse_freight_cents("free")


class MissingColumnsTests(unittest.TestCase):
    def test_reports_missing_in_order(self):
        self.assertEqual(
            logic.missing_columns(["line_id", "quantity"]),
            ["description", "unit_cost", "weight"],
        )

    def test_none_header_reports_all(self):
        self.assertEqual(logic.missing_columns(None), logic.REQUIRED_COLUMNS)


class BuildLineItemsTests(unittest.TestCase):
    def _row(self, line_no, **values):
        record = {
            "line_id": values.get("line_id", "L001"),
            "description": values.get("description", "Widget"),
            "quantity": values.get("quantity", "5"),
            "unit_cost": values.get("unit_cost", "10.00"),
            "weight": values.get("weight", "12.0"),
        }
        if "extra" in values:
            record[logic.EXTRA_KEY] = values["extra"]
        return (line_no, record)

    def test_valid_rows_build_items(self):
        rows = [self._row(2), self._row(3, line_id="L002")]
        items = logic.build_line_items(rows)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].value(), Decimal("50.00"))

    def test_empty_file_is_rejected(self):
        with self.assertRaises(logic.ValidationError):
            logic.build_line_items([])

    def test_collects_every_problem_at_once(self):
        rows = [
            self._row(2, quantity=""),  # missing quantity
            self._row(3, line_id="L003", quantity="abc"),  # non-numeric quantity
            self._row(4, line_id="L004", quantity="0"),  # zero quantity
            self._row(5, line_id="L001", quantity="2"),  # duplicate of line 2
            self._row(6, line_id="L006", extra=["surprise"]),  # extra field
        ]
        with self.assertRaises(logic.ValidationError) as caught:
            logic.build_line_items(rows)
        problems = caught.exception.problems
        # One problem per bad row above.
        self.assertEqual(len(problems), 5)
        joined = " ".join(problems)
        self.assertIn("Line 2", joined)
        self.assertIn("duplicate line_id", joined)
        self.assertIn("more fields than the header", joined)

    def test_negative_unit_cost_is_rejected(self):
        rows = [self._row(2, unit_cost="-1.00")]
        with self.assertRaises(logic.ValidationError):
            logic.build_line_items(rows)

    def test_missing_line_id_is_rejected(self):
        rows = [self._row(2, line_id="")]
        with self.assertRaises(logic.ValidationError):
            logic.build_line_items(rows)


if __name__ == "__main__":
    unittest.main()
