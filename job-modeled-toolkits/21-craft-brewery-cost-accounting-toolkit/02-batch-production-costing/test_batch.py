"""Unit tests for the batch production costing tool.

Run from this folder:
    python -m unittest -v
"""

import unittest
from decimal import Decimal

from batch import (
    allocate_by_weights,
    cost_batch,
    cost_per_litre,
    ingredient_cost,
    weighted_average_costs,
)
from validation import ValidationError, validate


def D(value):
    return Decimal(str(value))


# Weighted-average landed costs derived from the sample landed_costs.csv.
WAC = {
    "RM-MALT": Decimal("5050") / Decimal("4000"),      # 1.2625
    "RM-HOPS": Decimal("3936") / Decimal("200"),       # 19.68
    "PKG-CAN-355": Decimal("3750") / Decimal("40000"), # 0.09375
    "PKG-KEG-50L": Decimal("4576.42") / Decimal("100"),# 45.7642
    "PKG-LABEL": Decimal("813.58") / Decimal("40000"), # 0.0203395
}


class WacTests(unittest.TestCase):
    def test_weighted_average_blends_two_receipts(self):
        rows = [
            {"sku": "RM-MALT", "landed_total": "3750.00", "quantity": "3000"},
            {"sku": "RM-MALT", "landed_total": "1300.00", "quantity": "1000"},
        ]
        costs = weighted_average_costs(rows)
        self.assertEqual(costs["RM-MALT"], Decimal("1.2625"))


class AllocationTests(unittest.TestCase):
    def test_sums_to_amount(self):
        shares = allocate_by_weights(D("1637.19"), [D("1065"), D("750")])
        self.assertEqual(sum(shares), D("1637.19"))

    def test_single_run_takes_all(self):
        self.assertEqual(allocate_by_weights(D("690.86"), [D("1420")]), [D("690.86")])


class IngredientTests(unittest.TestCase):
    def test_lager_ingredient_cost(self):
        total, lines = ingredient_cost(
            [{"sku": "RM-MALT", "quantity": D("380")},
             {"sku": "RM-HOPS", "quantity": D("8")}], WAC)
        # 380 * 1.2625 = 479.75 ; 8 * 19.68 = 157.44
        self.assertEqual(lines[0]["cost"], D("479.75"))
        self.assertEqual(lines[1]["cost"], D("157.44"))
        self.assertEqual(total, D("637.19"))


class CostPerLitreTests(unittest.TestCase):
    def test_six_places(self):
        self.assertEqual(cost_per_litre(D("1637.19"), D("1815")), Decimal("0.902033"))


class BatchTests(unittest.TestCase):
    def batch(self, **kw):
        base = {
            "batch_id": "BATCH-L01", "beer": "Lager", "product_line": "Lager",
            "abv_class": "over_2_5", "brewed_litres": D("1900"),
            "finished_litres": D("1815"), "labour_cost": D("600"),
            "overhead_cost": D("400"),
        }
        base.update(kw)
        return base

    def test_lager_batch_totals_and_balance(self):
        ingredients = [{"sku": "RM-MALT", "quantity": D("380")},
                       {"sku": "RM-HOPS", "quantity": D("8")}]
        runs = [
            {"fg_sku": "FG-LAGER-CAN", "description": "can", "container_sku": "PKG-CAN-355",
             "label_sku": "PKG-LABEL", "units": D("3000"), "litres_per_unit": D("0.355")},
            {"fg_sku": "FG-LAGER-KEG", "description": "keg", "container_sku": "PKG-KEG-50L",
             "label_sku": "", "units": D("15"), "litres_per_unit": D("50")},
        ]
        summary, finished = cost_batch(self.batch(), ingredients, runs, WAC)
        self.assertEqual(summary["ingredient_cost"], D("637.19"))
        self.assertEqual(summary["brew_cost"], D("1637.19"))
        self.assertEqual(summary["volume_flag"], "")  # 1065 + 750 = 1815
        # The finished-unit line costs sum back to the total batch cost exactly.
        self.assertEqual(sum(f["line_cost"] for f in finished), summary["total_batch_cost"])
        # Packaging material: cans 3000 * (0.09375 + 0.0203395), kegs 15 * 45.7642.
        self.assertEqual(finished[0]["packaging_material_cost"], D("342.27"))
        self.assertEqual(finished[1]["packaging_material_cost"], D("686.46"))

    def test_volume_flag_when_packaging_short(self):
        runs = [{"fg_sku": "FG-LAGER-CAN", "description": "can", "container_sku": "PKG-CAN-355",
                 "label_sku": "PKG-LABEL", "units": D("1000"), "litres_per_unit": D("0.355")}]
        summary, _ = cost_batch(self.batch(), [{"sku": "RM-MALT", "quantity": D("380")}], runs, WAC)
        self.assertNotEqual(summary["volume_flag"], "")


class ValidationTests(unittest.TestCase):
    bh = list(__import__("validation").BATCH_COLUMNS)
    ih = list(__import__("validation").INGREDIENT_COLUMNS)
    rh = list(__import__("validation").RUN_COLUMNS)
    known = {"RM-MALT", "RM-HOPS", "PKG-CAN-355", "PKG-KEG-50L", "PKG-LABEL"}

    def good_batch(self, **kw):
        base = {"batch_id": "B1", "beer": "x", "product_line": "x", "abv_pct": "5",
                "abv_class": "over_2_5", "brewed_litres": "100", "finished_litres": "95",
                "labour_cost": "10", "overhead_cost": "5"}
        base.update(kw)
        return base

    def test_clean_passes(self):
        validate([self.good_batch()], self.bh,
                 [{"batch_id": "B1", "material_sku": "RM-MALT", "quantity": "10", "unit": "kg"}], self.ih,
                 [{"batch_id": "B1", "fg_sku": "FG-X", "description": "x", "container_sku": "PKG-CAN-355",
                   "label_sku": "PKG-LABEL", "units": "100", "litres_per_unit": "0.355"}], self.rh,
                 self.known)

    def test_finished_exceeds_brewed(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.good_batch(finished_litres="150")], self.bh, [], self.ih, [], self.rh, self.known)
        self.assertTrue(any("exceeds brewed" in p for p in ctx.exception.problems))

    def test_bad_abv_class(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.good_batch(abv_class="strong")], self.bh, [], self.ih, [], self.rh, self.known)
        self.assertTrue(any("abv_class" in p for p in ctx.exception.problems))

    def test_unknown_material(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.good_batch()], self.bh,
                     [{"batch_id": "B1", "material_sku": "RM-ZZ", "quantity": "10", "unit": "kg"}], self.ih,
                     [], self.rh, self.known)
        self.assertTrue(any("no landed cost" in p for p in ctx.exception.problems))

    def test_non_integer_units(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.good_batch()], self.bh, [], self.ih,
                     [{"batch_id": "B1", "fg_sku": "FG-X", "description": "x", "container_sku": "PKG-CAN-355",
                       "label_sku": "", "units": "100.5", "litres_per_unit": "0.355"}], self.rh, self.known)
        self.assertTrue(any("whole number" in p for p in ctx.exception.problems))

    def test_orphan_batch_reference(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.good_batch()], self.bh,
                     [{"batch_id": "B9", "material_sku": "RM-MALT", "quantity": "10", "unit": "kg"}], self.ih,
                     [], self.rh, self.known)
        self.assertTrue(any("not in the batch register" in p for p in ctx.exception.problems))


if __name__ == "__main__":
    unittest.main()
