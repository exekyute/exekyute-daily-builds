"""Unit tests for the costing engine.

Covers the weighted-average ledger, landed cost, unit conversion, the marginal
excise brackets, and every validation rule. Run with:
    python -m unittest -v
"""

import unittest
from decimal import Decimal

import costing
import validation


class LandedCostTests(unittest.TestCase):
    def test_landed_value_adds_freight_and_duty(self):
        # 100 kg at $15.00 plus $120 freight plus $90 duty = $1,710.00.
        self.assertEqual(
            costing.landed_value(100, "15.00", "120.00", "90.00"), Decimal("1710.00")
        )

    def test_landed_value_no_addons(self):
        self.assertEqual(costing.landed_value(1000, "1.20", "0", "0"), Decimal("1200.00"))


class WeightedAverageTests(unittest.TestCase):
    def test_two_receipts_then_issue(self):
        # Opening 1,000 kg at $1.20, then 2,000 kg landed at $2,680.00 total.
        qty, value = costing.update_weighted_average(0, "0", 1000, "1200.00")
        qty, value = costing.update_weighted_average(qty, value, 2000, "2680.00")
        self.assertEqual(qty, Decimal("3000"))
        self.assertEqual(value, Decimal("3880.00"))
        # Issue 2,500 kg at the blended $1.293333.../kg.
        cost = costing.issue_cost(qty, value, 2500)
        self.assertEqual(cost, Decimal("3233.33"))
        value = costing.money(value - cost)
        qty = qty - Decimal("2500")
        self.assertEqual(qty, Decimal("500"))
        self.assertEqual(value, Decimal("646.67"))
        self.assertEqual(costing.weighted_average_unit_cost(qty, value), Decimal("1.2933"))

    def test_issue_from_empty_balance_costs_zero(self):
        self.assertEqual(costing.issue_cost(0, "0", 10), Decimal("0.00"))

    def test_unit_cost_of_empty_balance(self):
        self.assertEqual(costing.weighted_average_unit_cost(0, "0"), Decimal("0.0000"))


class LedgerTests(unittest.TestCase):
    def _txn(self, txn_type, quantity, unit_price="0", freight="0", customs_duty="0"):
        return {
            "txn_type": txn_type,
            "quantity": Decimal(quantity),
            "unit_price": Decimal(unit_price),
            "freight": Decimal(freight),
            "customs_duty": Decimal(customs_duty),
        }

    def test_hops_ledger_matches_hand_check(self):
        result = costing.run_ledger(
            [
                self._txn("opening", "200", "14.00"),
                self._txn("receipt", "100", "15.00", "120.00", "90.00"),
                self._txn("issue", "250"),
            ]
        )
        self.assertEqual(result["on_hand_qty"], Decimal("50"))
        self.assertEqual(result["on_hand_value"], Decimal("751.67"))
        self.assertEqual(result["wac_unit_cost"], Decimal("15.0334"))
        self.assertEqual(result["integrity_flag"], "")

    def test_negative_on_hand_is_flagged(self):
        result = costing.run_ledger(
            [self._txn("opening", "20000", "0.02"), self._txn("issue", "25000")]
        )
        self.assertEqual(result["on_hand_qty"], Decimal("-5000"))
        self.assertEqual(result["integrity_flag"], "negative on-hand")


class UnitConversionTests(unittest.TestCase):
    def test_volume_units(self):
        self.assertEqual(costing.to_litres(5, "hl"), Decimal("500"))
        self.assertEqual(costing.to_litres(1, "bbl"), Decimal("117.347765"))

    def test_discrete_unit_uses_litres_per_unit(self):
        # 500 cases at 8.52 L per case.
        self.assertEqual(costing.to_litres(500, "case", "8.52"), Decimal("4260.00"))

    def test_discrete_unit_without_factor_raises(self):
        with self.assertRaises(ValueError):
            costing.to_litres(10, "keg")

    def test_litres_to_hectolitres(self):
        self.assertEqual(costing.litres_to_hectolitres("4260"), Decimal("42.60"))


class ExciseTests(unittest.TestCase):
    def test_single_bracket(self):
        # 100 hL starting from 0 sits entirely in the first bracket.
        duty, after = costing.excise_for_volume("100", "over_2_5", "0")
        self.assertEqual(duty, Decimal("376.900"))
        self.assertEqual(after, Decimal("100"))

    def test_spans_two_brackets(self):
        # 71.90 hL of strong beer from 1,960 hL crosses the 2,000 hL line:
        # 40.00 hL at $3.769 plus 31.90 hL at $7.538.
        duty, after = costing.excise_for_volume("71.90", "over_2_5", "1960")
        self.assertEqual(costing.money(duty), Decimal("391.22"))
        self.assertEqual(after, Decimal("2031.90"))

    def test_radler_second_bracket(self):
        # 8.52 hL of mid-strength beer sitting above 2,000 hL at $3.770.
        duty, after = costing.excise_for_volume("8.52", "over_1_2_to_2_5", "2031.90")
        self.assertEqual(costing.money(duty), Decimal("32.12"))


class ValidationTests(unittest.TestCase):
    BASE = {
        "txn_id": "T1",
        "date": "2026-05-01",
        "sku": "RM-MALT",
        "description": "Malt",
        "category": "raw_material",
        "txn_type": "receipt",
        "quantity": "100",
        "unit": "kg",
        "unit_price": "1.20",
        "freight": "0",
        "customs_duty": "0",
        "abv_class": "",
        "litres_per_unit": "",
    }

    def row(self, **overrides):
        data = dict(self.BASE)
        data.update(overrides)
        return data

    def test_clean_row_passes(self):
        self.assertEqual(validation.validate_rows([self.row()]), [])

    def test_missing_column_caught(self):
        errors = validation.validate_header(["txn_id", "sku"])
        self.assertTrue(errors and "Missing required column" in errors[0])

    def test_duplicate_txn_id(self):
        errors = validation.validate_rows([self.row(), self.row()])
        self.assertTrue(any("duplicate txn_id" in e for e in errors))

    def test_non_positive_quantity(self):
        errors = validation.validate_rows([self.row(quantity="-50")])
        self.assertTrue(any("quantity must be greater than zero" in e for e in errors))

    def test_non_numeric_quantity(self):
        errors = validation.validate_rows([self.row(quantity="abc")])
        self.assertTrue(any("is not a number" in e for e in errors))

    def test_bad_category(self):
        errors = validation.validate_rows([self.row(category="grain")])
        self.assertTrue(any("category 'grain'" in e for e in errors))

    def test_receipt_needs_unit_price(self):
        errors = validation.validate_rows([self.row(unit_price="")])
        self.assertTrue(any("needs a unit_price" in e for e in errors))

    def test_opening_cannot_carry_freight(self):
        errors = validation.validate_rows(
            [self.row(txn_type="opening", freight="10.00")]
        )
        self.assertTrue(any("opening balance cannot carry freight" in e for e in errors))

    def test_package_needs_abv_class_and_litres(self):
        errors = validation.validate_rows(
            [
                self.row(
                    txn_type="package",
                    category="finished_goods",
                    unit="case",
                    abv_class="",
                    litres_per_unit="",
                )
            ]
        )
        self.assertTrue(any("needs an abv_class" in e for e in errors))
        self.assertTrue(any("needs litres_per_unit" in e for e in errors))

    def test_abv_class_only_on_package(self):
        errors = validation.validate_rows([self.row(abv_class="over_2_5")])
        self.assertTrue(any("only belongs on a package" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
