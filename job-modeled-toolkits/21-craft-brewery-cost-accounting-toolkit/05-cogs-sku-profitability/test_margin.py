"""Unit tests for the COGS and margin tool.

Run from this folder:
    python -m unittest -v
"""

import unittest
from decimal import Decimal

from margin import (
    by_product_line,
    class_packaged_litres,
    cost_sales,
    excise_rate_per_litre,
    margin_line,
    sku_cost_basis,
)
from validation import ValidationError, validate


def D(value):
    return Decimal(str(value))


FINISHED = [
    {"fg_sku": "FG-LAGER-CAN", "product_line": "Lager", "abv_class": "over_2_5",
     "units": "3000", "packaged_litres": "1065.000", "line_cost": "1302.94"},
    {"fg_sku": "FG-LAGER-KEG", "product_line": "Lager", "abv_class": "over_2_5",
     "units": "15", "packaged_litres": "750", "line_cost": "1362.98"},
    {"fg_sku": "FG-IPA-CAN", "product_line": "IPA", "abv_class": "over_2_5",
     "units": "2000", "packaged_litres": "710.000", "line_cost": "1317.84"},
    {"fg_sku": "FG-IPA-KEG", "product_line": "IPA", "abv_class": "over_2_5",
     "units": "10", "packaged_litres": "500", "line_cost": "1225.01"},
    {"fg_sku": "FG-RADLER-CAN", "product_line": "Radler", "abv_class": "over_1_2_to_2_5",
     "units": "4000", "packaged_litres": "1420.000", "line_cost": "1147.22"},
]
EXCISE = [
    {"abv_class": "over_2_5", "excise_duty": "114.01"},
    {"abv_class": "over_1_2_to_2_5", "excise_duty": "35.16"},
]


class RateTests(unittest.TestCase):
    def test_class_litres(self):
        litres = class_packaged_litres(FINISHED)
        self.assertEqual(litres["over_2_5"], D("3025.000"))
        self.assertEqual(litres["over_1_2_to_2_5"], D("1420.000"))

    def test_rate_per_litre(self):
        rates = excise_rate_per_litre(EXCISE, class_packaged_litres(FINISHED))
        self.assertEqual(rates["over_2_5"], D("114.01") / D("3025.000"))


class MarginTests(unittest.TestCase):
    def basis(self):
        rates = excise_rate_per_litre(EXCISE, class_packaged_litres(FINISHED))
        return sku_cost_basis(FINISHED, rates)

    def test_lager_can_retail_line(self):
        line = margin_line(
            {"fg_sku": "FG-LAGER-CAN", "channel": "retail",
             "units_sold": D("2500"), "unit_price": D("2.50")}, self.basis())
        self.assertEqual(line["revenue"], D("6250.00"))
        self.assertEqual(line["cogs_production"], D("1085.78"))
        self.assertEqual(line["cogs_excise"], D("33.45"))
        self.assertEqual(line["cogs_total"], D("1119.23"))
        self.assertEqual(line["gross_margin"], D("5130.77"))
        self.assertEqual(line["margin_pct"], D("82.09"))

    def test_product_line_rollup_sums(self):
        sales = [
            {"fg_sku": "FG-IPA-CAN", "channel": "retail", "units_sold": D("1200"), "unit_price": D("2.95")},
            {"fg_sku": "FG-IPA-CAN", "channel": "distributor", "units_sold": D("500"), "unit_price": D("2.60")},
        ]
        lines = cost_sales(sales, self.basis())
        rolled = by_product_line(lines)
        ipa = [r for r in rolled if r["product_line"] == "IPA"][0]
        self.assertEqual(ipa["revenue"], sum(l["revenue"] for l in lines))
        self.assertEqual(ipa["gross_margin"], sum(l["gross_margin"] for l in lines))


class ValidationTests(unittest.TestCase):
    header = list(__import__("validation").SALES_COLUMNS)

    def basis(self):
        rates = excise_rate_per_litre(EXCISE, class_packaged_litres(FINISHED))
        return sku_cost_basis(FINISHED, rates)

    def row(self, **kw):
        base = {"fg_sku": "FG-LAGER-CAN", "channel": "retail", "units_sold": "100", "unit_price": "2.50"}
        base.update(kw)
        return base

    def test_clean_passes(self):
        validate([self.row()], self.header, self.basis())

    def test_unknown_sku(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(fg_sku="FG-ZZ")], self.header, self.basis())
        self.assertTrue(any("was not produced" in p for p in ctx.exception.problems))

    def test_bad_channel(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(channel="wholesale")], self.header, self.basis())
        self.assertTrue(any("channel" in p for p in ctx.exception.problems))

    def test_sells_more_than_made(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(fg_sku="FG-RADLER-CAN", units_sold="5000")], self.header, self.basis())
        self.assertTrue(any("exceed units produced" in p for p in ctx.exception.problems))

    def test_zero_price(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(unit_price="0")], self.header, self.basis())
        self.assertTrue(any("unit_price" in p for p in ctx.exception.problems))


if __name__ == "__main__":
    unittest.main()
