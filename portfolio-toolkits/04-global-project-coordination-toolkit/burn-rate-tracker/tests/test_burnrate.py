"""Unit tests for the Milestone-Driven Burn Rate Tracker logic and validation."""

import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from burnrate import burn_rate, process_phases, remaining  # noqa: E402
from validators import (  # noqa: E402
    InvalidPhase,
    validate_cost,
    validate_phase_name,
)


def row(phase, cost):
    return {"phase": phase, "cost": cost}


class BurnRateTests(unittest.TestCase):
    def test_starting_position_matches_ledger(self):
        # 248600 / 250000 = 99.44% (the hand-checked cross-tool value).
        self.assertEqual(burn_rate(Decimal("248600.00"), Decimal("250000.00")),
                         Decimal("99.44"))

    def test_over_fund_rate(self):
        # 250500 / 250000 = 100.20%.
        self.assertEqual(burn_rate(Decimal("250500.00"), Decimal("250000.00")),
                         Decimal("100.20"))

    def test_remaining_can_go_negative(self):
        self.assertEqual(remaining(Decimal("250000.00"), Decimal("250500.00")),
                         Decimal("-500.00"))

    def test_zero_fund_rejected(self):
        with self.assertRaises(ValueError):
            burn_rate(Decimal("10.00"), Decimal("0"))


class ValidationTests(unittest.TestCase):
    def test_blank_phase_name_rejected(self):
        with self.assertRaises(InvalidPhase):
            validate_phase_name("   ")

    def test_blank_cost_rejected(self):
        with self.assertRaises(InvalidPhase):
            validate_cost("")

    def test_non_numeric_cost_rejected(self):
        with self.assertRaises(InvalidPhase):
            validate_cost("not-a-number")

    def test_non_positive_cost_rejected(self):
        with self.assertRaises(InvalidPhase):
            validate_cost("0")


class ProcessPhasesTests(unittest.TestCase):
    def build(self):
        records = [
            row("Inception Report", "500.00"),
            row("Field Survey", "600.00"),
            row("Midterm Review", "800.00"),
            row("Field Survey", "300.00"),
            row("Final Audit", ""),
            row("Closeout", "not-a-number"),
        ]
        return process_phases(records, Decimal("250000.00"), Decimal("248600.00"))

    def test_seeded_batch_counts(self):
        result = self.build()
        self.assertEqual(result.phase_count, 3)
        self.assertEqual(len(result.skipped), 2)     # blank cost, non-numeric cost
        self.assertEqual(len(result.duplicates), 1)  # repeated Field Survey

    def test_running_totals_and_over_fund(self):
        result = self.build()
        first, second, third = result.lines
        self.assertEqual(first.spent, Decimal("249100.00"))
        self.assertFalse(first.over_fund)
        self.assertEqual(second.spent, Decimal("249700.00"))
        self.assertFalse(second.over_fund)
        self.assertEqual(third.spent, Decimal("250500.00"))
        self.assertTrue(third.over_fund)

    def test_final_summary(self):
        result = self.build()
        self.assertEqual(result.final_spent, Decimal("250500.00"))
        self.assertEqual(result.final_remaining, Decimal("-500.00"))
        self.assertEqual(result.final_burn_rate, Decimal("100.20"))
        self.assertTrue(result.over_fund)

    def test_duplicate_does_not_add_cost(self):
        records = [row("Phase A", "100.00"), row("Phase A", "999.00")]
        result = process_phases(records, Decimal("250000.00"), Decimal("0"))
        self.assertEqual(result.phase_count, 1)
        self.assertEqual(result.final_spent, Decimal("100.00"))


if __name__ == "__main__":
    unittest.main()
