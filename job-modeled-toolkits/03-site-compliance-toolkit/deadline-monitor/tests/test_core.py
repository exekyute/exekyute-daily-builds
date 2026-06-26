"""Tests for the deadline monitor's core logic.

These check the parts most likely to go wrong: parsing dates strictly, sorting
items into the right urgency band (including the exact boundaries of 0 days and
14 days), rejecting bad rows, and finding sites with activity but no deadline.

Run from the tool folder with:
    python -m unittest discover tests
"""

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core

TODAY = date(2026, 6, 6)


class TestParseDate(unittest.TestCase):
    def test_good_date(self):
        self.assertEqual(core.parse_date("2026-06-06"), date(2026, 6, 6))

    def test_slash_format_rejected(self):
        with self.assertRaises(ValueError):
            core.parse_date("06/06/2026")

    def test_missing_leading_zero_rejected(self):
        with self.assertRaises(ValueError):
            core.parse_date("2026-6-6")

    def test_impossible_day_rejected(self):
        with self.assertRaises(ValueError):
            core.parse_date("2026-02-30")


class TestClassify(unittest.TestCase):
    def test_overdue(self):
        band, days = core.classify(date(2026, 5, 20), TODAY)
        self.assertEqual(band, core.OVERDUE)
        self.assertEqual(days, -17)

    def test_due_today_boundary(self):
        band, days = core.classify(date(2026, 6, 6), TODAY)
        self.assertEqual(band, core.DUE_TODAY)
        self.assertEqual(days, 0)

    def test_due_soon_one_day(self):
        band, _ = core.classify(date(2026, 6, 7), TODAY)
        self.assertEqual(band, core.DUE_SOON)

    def test_due_soon_upper_boundary_14_days(self):
        band, days = core.classify(date(2026, 6, 20), TODAY)
        self.assertEqual(band, core.DUE_SOON)
        self.assertEqual(days, 14)

    def test_upcoming_just_past_boundary_15_days(self):
        band, days = core.classify(date(2026, 6, 21), TODAY)
        self.assertEqual(band, core.UPCOMING)
        self.assertEqual(days, 15)


class TestValidateRow(unittest.TestCase):
    def test_clean_row(self):
        record, error, note = core.validate_log_row({
            "site": "North Site", "requirement": "Permit",
            "due_date": "2026-06-20", "status": "open"})
        self.assertIsNone(error)
        self.assertIsNone(note)
        self.assertEqual(record["due_date"], date(2026, 6, 20))

    def test_blank_site_rejected(self):
        record, error, _ = core.validate_log_row({
            "site": "", "requirement": "Permit",
            "due_date": "2026-06-20", "status": "open"})
        self.assertIsNone(record)
        self.assertEqual(error, "missing site")

    def test_bad_date_rejected(self):
        record, error, _ = core.validate_log_row({
            "site": "North Site", "requirement": "Permit",
            "due_date": "06/01/2026", "status": "open"})
        self.assertIsNone(record)
        self.assertIn("YYYY-MM-DD", error)

    def test_unknown_status_becomes_open_with_note(self):
        record, error, note = core.validate_log_row({
            "site": "North Site", "requirement": "Permit",
            "due_date": "2026-07-15", "status": "pending"})
        self.assertIsNone(error)
        self.assertEqual(record["status"], "open")
        self.assertIn("pending", note)


class TestCrossCheck(unittest.TestCase):
    def test_finds_site_with_activity_but_no_deadline(self):
        log_records = [
            {"site": "North Site"},
            {"site": "Harbor Site"},
        ]
        ledger_sites = ["Harbor Site", "North Site", "Ridge Site"]
        gaps = core.cross_check(log_records, ledger_sites)
        self.assertEqual(gaps, ["Ridge Site"])

    def test_no_ledger_means_no_gaps(self):
        self.assertEqual(core.cross_check([{"site": "North Site"}], None), [])


class TestBuildDashboard(unittest.TestCase):
    def test_complete_item_goes_to_complete_band(self):
        records = [{
            "site": "North Site", "requirement": "Q1 report",
            "due_date": date(2026, 4, 15), "status": "complete"}]
        bands = core.build_dashboard(records, TODAY)
        self.assertEqual(len(bands[core.COMPLETE]), 1)
        self.assertEqual(len(bands[core.OVERDUE]), 0)


if __name__ == "__main__":
    unittest.main()
