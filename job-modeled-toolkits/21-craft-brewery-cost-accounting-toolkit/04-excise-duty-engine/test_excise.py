"""Unit tests for the excise duty engine.

Run from this folder:
    python -m unittest -v
"""

import unittest
from decimal import Decimal

from excise import (
    excise_for_volume,
    litres_to_hectolitres,
    run_excise,
    total_duty,
)
from validation import ValidationError, validate


def D(value):
    return Decimal(str(value))


class ConversionTests(unittest.TestCase):
    def test_litres_to_hectolitres(self):
        self.assertEqual(litres_to_hectolitres(D("1065")), D("10.65"))


class BracketTests(unittest.TestCase):
    def test_within_first_bracket(self):
        duty, after = excise_for_volume(D("10.65"), "over_2_5", D("1960"))
        self.assertEqual(duty, D("10.65") * D("3.769"))
        self.assertEqual(after, D("1970.65"))

    def test_crosses_first_boundary(self):
        # 14.20 hL starting at 1990.25: 9.75 in bracket 1, 4.45 in bracket 2.
        duty, after = excise_for_volume(D("14.20"), "over_1_2_to_2_5", D("1990.25"))
        expected = D("9.75") * D("1.885") + D("4.45") * D("3.770")
        self.assertEqual(duty, expected)
        self.assertEqual(after, D("2004.45"))

    def test_unknown_class_raises(self):
        with self.assertRaises(ValueError):
            excise_for_volume(D("10"), "strong", D("0"))


class RunExciseTests(unittest.TestCase):
    EVENTS = [
        {"abv_class": "over_2_5", "litres": D("1065.000")},
        {"abv_class": "over_2_5", "litres": D("750")},
        {"abv_class": "over_2_5", "litres": D("710.000")},
        {"abv_class": "over_2_5", "litres": D("500")},
        {"abv_class": "over_1_2_to_2_5", "litres": D("1420.000")},
    ]

    def test_period_totals(self):
        summary, cumulative = run_excise(self.EVENTS, D("1960.00"))
        by_class = {r["abv_class"]: r for r in summary}
        self.assertEqual(by_class["over_2_5"]["hectolitres"], D("30.25"))
        self.assertEqual(by_class["over_2_5"]["excise_duty"], D("114.01"))
        self.assertEqual(by_class["over_1_2_to_2_5"]["hectolitres"], D("14.20"))
        self.assertEqual(by_class["over_1_2_to_2_5"]["excise_duty"], D("35.16"))
        self.assertEqual(cumulative, D("2004.45"))

    def test_total_duty(self):
        summary, _ = run_excise(self.EVENTS, D("1960.00"))
        self.assertEqual(total_duty(summary), D("149.17"))


class ValidationTests(unittest.TestCase):
    header = list(__import__("validation").REQUIRED_COLUMNS)

    def row(self, **kw):
        base = {"fg_sku": "FG-X", "abv_class": "over_2_5", "packaged_litres": "1000"}
        base.update(kw)
        return base

    def test_clean_passes(self):
        validate([self.row()], self.header, "1960.00")

    def test_bad_abv_class(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(abv_class="strong")], self.header, "0")
        self.assertTrue(any("abv_class" in p for p in ctx.exception.problems))

    def test_negative_litres(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(packaged_litres="-5")], self.header, "0")
        self.assertTrue(any("packaged_litres" in p for p in ctx.exception.problems))

    def test_blank_fg_sku(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row(fg_sku="")], self.header, "0")
        self.assertTrue(any("fg_sku" in p for p in ctx.exception.problems))

    def test_negative_ytd(self):
        with self.assertRaises(ValidationError) as ctx:
            validate([self.row()], self.header, "-1")
        self.assertTrue(any("ytd-hl" in p for p in ctx.exception.problems))


if __name__ == "__main__":
    unittest.main()
