"""Tests for the fixed-asset depreciation engine.

Covers the book depreciation math, each branch of the CCA rollforward (clean
half-year addition, recapture, terminal loss, and a fully written-off pool), the
end-to-end run against the sample register, and every validation rule.

Run from this folder:
  python -m unittest
"""

import csv
import unittest
from decimal import Decimal

from cca import book_depreciation, class_cca, compute_schedules
from validation import validate_asset_row, validate_opening_row, ValidationError


def D(value):
    return Decimal(value)


class BookDepreciationTests(unittest.TestCase):
    def test_straight_line_first_year(self):
        result = book_depreciation(D("8000.00"), D("0.00"), 10, D("0.00"))
        self.assertEqual(result["annual_book_dep"], D("800.00"))
        self.assertEqual(result["current_book_dep"], D("800.00"))
        self.assertEqual(result["accum_book_dep"], D("800.00"))
        self.assertEqual(result["net_book_value"], D("7200.00"))

    def test_salvage_reduces_base(self):
        result = book_depreciation(D("5000.00"), D("500.00"), 5, D("0.00"))
        self.assertEqual(result["annual_book_dep"], D("900.00"))

    def test_fully_depreciated_takes_zero(self):
        result = book_depreciation(D("1200.00"), D("0.00"), 3, D("1200.00"))
        self.assertEqual(result["current_book_dep"], D("0.00"))
        self.assertEqual(result["net_book_value"], D("0.00"))

    def test_final_year_caps_at_remaining(self):
        result = book_depreciation(D("1000.00"), D("0.00"), 3, D("700.00"))
        self.assertEqual(result["current_book_dep"], D("300.00"))


class ClassCcaTests(unittest.TestCase):
    def test_clean_half_year_addition(self):
        row = class_cca("8", D("10000.00"), D("5000.00"), D("0.00"), assets_remaining=2)
        self.assertEqual(row["half_year_adjustment"], D("2500.00"))
        self.assertEqual(row["cca_base"], D("12500.00"))
        self.assertEqual(row["cca"], D("2500.00"))
        self.assertEqual(row["closing_ucc"], D("12500.00"))
        self.assertEqual(row["recapture"], D("0.00"))
        self.assertEqual(row["terminal_loss"], D("0.00"))

    def test_recapture_on_negative_pool(self):
        row = class_cca("10", D("4000.00"), D("0.00"), D("7000.00"), assets_remaining=0)
        self.assertEqual(row["recapture"], D("3000.00"))
        self.assertEqual(row["cca"], D("0.00"))
        self.assertEqual(row["closing_ucc"], D("0.00"))

    def test_terminal_loss_when_no_assets_remain(self):
        row = class_cca("50", D("1200.00"), D("0.00"), D("300.00"), assets_remaining=0)
        self.assertEqual(row["terminal_loss"], D("900.00"))
        self.assertEqual(row["cca"], D("0.00"))
        self.assertEqual(row["closing_ucc"], D("0.00"))

    def test_zero_pool_takes_no_cca(self):
        row = class_cca("12", D("0.00"), D("0.00"), D("0.00"), assets_remaining=1)
        self.assertEqual(row["cca"], D("0.00"))
        self.assertEqual(row["closing_ucc"], D("0.00"))
        self.assertEqual(row["terminal_loss"], D("0.00"))

    def test_no_half_year_without_net_additions(self):
        row = class_cca("8", D("10000.00"), D("0.00"), D("0.00"), assets_remaining=1)
        self.assertEqual(row["half_year_adjustment"], D("0.00"))
        self.assertEqual(row["cca"], D("2000.00"))
        self.assertEqual(row["closing_ucc"], D("8000.00"))


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        with open("sample_assets.csv", newline="", encoding="utf-8") as handle:
            self.assets = [validate_asset_row(r) for r in csv.DictReader(handle)]
        opening = {}
        with open("opening_ucc.csv", newline="", encoding="utf-8") as handle:
            for r in csv.DictReader(handle):
                cca_class, value = validate_opening_row(r)
                opening[cca_class] = value
        self.opening = opening
        self.per_asset, self.per_class = compute_schedules(self.assets, self.opening, 2026)
        self.by_class = {row["cca_class"]: row for row in self.per_class}

    def test_class_8_headline_reconciles(self):
        row = self.by_class["8"]
        self.assertEqual(row["cca"], D("2500.00"))
        self.assertEqual(row["closing_ucc"], D("12500.00"))
        self.assertEqual(row["net_book_value"], D("5700.00"))
        self.assertEqual(row["temporary_difference"], D("-6800.00"))

    def test_class_10_recapture(self):
        self.assertEqual(self.by_class["10"]["recapture"], D("3000.00"))

    def test_class_50_terminal_loss(self):
        self.assertEqual(self.by_class["50"]["terminal_loss"], D("900.00"))

    def test_class_12_zero(self):
        self.assertEqual(self.by_class["12"]["cca"], D("0.00"))
        self.assertEqual(self.by_class["12"]["closing_ucc"], D("0.00"))

    def test_rollforward_identity_holds_for_every_class(self):
        # opening + additions - disposals - cca - recapture-reset/terminal must
        # land on the reported closing UCC for each class.
        for row in self.per_class:
            pool_before = row["opening_ucc"] + row["additions"] - row["disposals"]
            if row["recapture"] > D("0.00") or row["terminal_loss"] > D("0.00"):
                self.assertEqual(row["closing_ucc"], D("0.00"))
            else:
                self.assertEqual(row["closing_ucc"], pool_before - row["cca"])


class ValidationTests(unittest.TestCase):
    def _row(self, **overrides):
        base = {
            "asset_id": "FA-900",
            "description": "Test asset",
            "cca_class": "8",
            "capital_cost": "1000.00",
            "in_service_date": "2026-01-01",
            "useful_life_years": "5",
            "salvage_value": "0.00",
            "disposed": "N",
            "disposal_proceeds": "",
            "prior_accum_book_dep": "0.00",
        }
        base.update(overrides)
        return base

    def test_clean_row_parses(self):
        parsed = validate_asset_row(self._row())
        self.assertEqual(parsed["capital_cost"], D("1000.00"))
        self.assertEqual(parsed["in_service_year"], 2026)
        self.assertFalse(parsed["disposed"])

    def test_unknown_class_rejected(self):
        with self.assertRaises(ValidationError):
            validate_asset_row(self._row(cca_class="99"))

    def test_negative_cost_rejected(self):
        with self.assertRaises(ValidationError):
            validate_asset_row(self._row(capital_cost="-1.00"))

    def test_missing_life_rejected(self):
        with self.assertRaises(ValidationError):
            validate_asset_row(self._row(useful_life_years=""))

    def test_bad_date_rejected(self):
        with self.assertRaises(ValidationError):
            validate_asset_row(self._row(in_service_date="01-01-2026"))

    def test_salvage_above_cost_rejected(self):
        with self.assertRaises(ValidationError):
            validate_asset_row(self._row(salvage_value="2000.00"))

    def test_bad_disposed_flag_rejected(self):
        with self.assertRaises(ValidationError):
            validate_asset_row(self._row(disposed="maybe"))

    def test_disposed_requires_proceeds(self):
        with self.assertRaises(ValidationError):
            validate_asset_row(self._row(disposed="Y", disposal_proceeds=""))

    def test_prior_accum_above_base_rejected(self):
        with self.assertRaises(ValidationError):
            validate_asset_row(self._row(prior_accum_book_dep="5000.00"))

    def test_opening_unknown_class_rejected(self):
        with self.assertRaises(ValidationError):
            validate_opening_row({"cca_class": "77", "opening_ucc": "100.00"})


if __name__ == "__main__":
    unittest.main()
