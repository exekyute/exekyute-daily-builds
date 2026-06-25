"""Tests for the aggregator's core logic.

These check the trickiest parts: translating different column names, rejecting
bad quantities and months, deduplicating, and formatting quantities cleanly. If
you change a rule later, these tests tell you right away if something broke.

Run from the tool folder with:
    python -m unittest discover tests
"""

import os
import sys
import unittest
from decimal import Decimal

# Make the parent folder importable so we can load core.py when the tests are
# run from inside the tests/ folder.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core


class TestHeaderMap(unittest.TestCase):
    def test_standard_headers_map(self):
        header_map, missing = core.build_header_map(
            ["Site", "Month", "Waste (tons)", "Fuel (gal)"]
        )
        self.assertEqual(missing, [])
        self.assertEqual(header_map["site"], "Site")
        self.assertEqual(header_map["fuel_gallons"], "Fuel (gal)")

    def test_alternate_headers_map(self):
        header_map, missing = core.build_header_map(
            ["Location", "Reporting Month", "Waste Tonnage", "Diesel Gallons"]
        )
        self.assertEqual(missing, [])
        self.assertEqual(header_map["site"], "Location")
        self.assertEqual(header_map["waste_tons"], "Waste Tonnage")

    def test_messy_spacing_and_case_still_match(self):
        header_map, missing = core.build_header_map(
            ["  facility ", "PERIOD", "waste_tons", "FUEL USED"]
        )
        self.assertEqual(missing, [])
        self.assertEqual(header_map["site"], "  facility ")

    def test_missing_column_is_reported(self):
        header_map, missing = core.build_header_map(["Site", "Month", "Fuel (gal)"])
        self.assertIn("waste_tons", missing)


class TestParsing(unittest.TestCase):
    def test_good_month(self):
        self.assertEqual(core.parse_month("2026-01"), "2026-01")

    def test_bad_month_shape(self):
        with self.assertRaises(ValueError):
            core.parse_month("2026/01")

    def test_month_out_of_range(self):
        with self.assertRaises(ValueError):
            core.parse_month("2026-13")

    def test_good_quantity(self):
        self.assertEqual(core.parse_quantity("12.5", "waste_tons"), Decimal("12.5"))

    def test_zero_quantity_is_allowed(self):
        self.assertEqual(core.parse_quantity("0", "waste_tons"), Decimal("0"))

    def test_negative_quantity_rejected(self):
        with self.assertRaises(ValueError):
            core.parse_quantity("-5.0", "fuel_gallons")

    def test_non_numeric_quantity_rejected(self):
        with self.assertRaises(ValueError):
            core.parse_quantity("none", "fuel_gallons")


class TestValidateRow(unittest.TestCase):
    def setUp(self):
        self.header_map = {
            "site": "Site",
            "month": "Month",
            "waste_tons": "Waste (tons)",
            "fuel_gallons": "Fuel (gal)",
        }

    def test_clean_row(self):
        row = {"Site": "North Site", "Month": "2026-01",
               "Waste (tons)": "12.5", "Fuel (gal)": "340.0"}
        record, error = core.validate_row(row, self.header_map)
        self.assertIsNone(error)
        self.assertEqual(record["site"], "North Site")

    def test_blank_site_rejected(self):
        row = {"Site": "", "Month": "2026-01",
               "Waste (tons)": "1.0", "Fuel (gal)": "10.0"}
        record, error = core.validate_row(row, self.header_map)
        self.assertIsNone(record)
        self.assertEqual(error, "missing site")


class TestCombineFormatting(unittest.TestCase):
    def test_format_quantity_is_fixed_point(self):
        self.assertEqual(core.format_quantity(Decimal("12.5")), "12.50")
        self.assertEqual(core.format_quantity(Decimal("0")), "0.00")

    def test_format_quantity_rounds_half_up(self):
        self.assertEqual(core.format_quantity(Decimal("1.005")), "1.01")


if __name__ == "__main__":
    unittest.main()
