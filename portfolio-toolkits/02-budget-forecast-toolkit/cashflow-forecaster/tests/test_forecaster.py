"""Tests for the cash flow forecaster.

Run from the repository root:
    python -m unittest discover -s cashflow-forecaster/tests -v
"""

import os
import sys
import tempfile
import unittest
from decimal import Decimal

# Make the tool's modules (one directory up) importable.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from forecaster import (
    has_enough_data,
    next_periods,
    project,
    runway_months,
    simple_moving_average,
    weighted_moving_average,
)
from loader import HistoryError, load_history

FLOWS = [
    Decimal("-22000.00"),
    Decimal("-18000.00"),
    Decimal("-20000.00"),
]


class MovingAverageTests(unittest.TestCase):
    def test_simple_average_of_last_window(self):
        self.assertEqual(simple_moving_average(FLOWS, 3), Decimal("-20000.00"))

    def test_simple_average_uses_only_the_window(self):
        flows = [Decimal("100.00")] + FLOWS
        self.assertEqual(simple_moving_average(flows, 3), Decimal("-20000.00"))

    def test_weighted_average_favors_recent(self):
        # (1*-22000 + 2*-18000 + 3*-20000) / 6 = -19666.6667 -> -19666.67
        self.assertEqual(weighted_moving_average(FLOWS, 3), Decimal("-19666.67"))


class RunwayTests(unittest.TestCase):
    def test_runway_when_burning_cash(self):
        self.assertEqual(
            runway_months(Decimal("250000.00"), Decimal("-20000.00")),
            Decimal("12.50"),
        )

    def test_no_runway_when_cash_positive(self):
        self.assertIsNone(runway_months(Decimal("250000.00"), Decimal("5000.00")))

    def test_no_runway_when_flat(self):
        self.assertIsNone(runway_months(Decimal("250000.00"), Decimal("0.00")))


class NextPeriodTests(unittest.TestCase):
    def test_increments_month_and_rolls_year(self):
        self.assertEqual(next_periods("2025-12", 3), ["2026-01", "2026-02", "2026-03"])

    def test_falls_back_for_non_date_label(self):
        self.assertEqual(next_periods("Q3", 2), ["Next 1", "Next 2"])


class ProjectionTests(unittest.TestCase):
    def test_running_balance(self):
        rows = project(Decimal("250000.00"), Decimal("-20000.00"), ["a", "b", "c"])
        self.assertEqual(rows[0]["balance"], Decimal("230000.00"))
        self.assertEqual(rows[-1]["balance"], Decimal("190000.00"))


class EnoughDataTests(unittest.TestCase):
    def test_minimum_data_boundary(self):
        self.assertTrue(has_enough_data([1, 2, 3], 3))
        self.assertFalse(has_enough_data([1, 2], 3))


class LoadHistoryTests(unittest.TestCase):
    def _write(self, text):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".csv", delete=False, newline="", encoding="utf-8"
        )
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_skips_blank_and_bad_and_counts_duplicates(self):
        path = self._write(
            "period,net_cash_flow\n"
            "2025-11,-22000.00\n"
            "2025-12,-18000.00\n"
            "2025-12,-5000.00\n"  # duplicate period, kept first
            "2026-01,\n"  # blank, skipped
            "2026-02,abc\n"  # unreadable, skipped
        )
        result = load_history(path)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[1], ("2025-12", Decimal("-18000.00")))
        self.assertEqual(result.duplicates, 1)
        self.assertEqual(result.skipped, 2)

    def test_missing_column_raises(self):
        path = self._write("period,cash\n2025-11,-22000.00\n")
        with self.assertRaises(HistoryError):
            load_history(path)


if __name__ == "__main__":
    unittest.main()
