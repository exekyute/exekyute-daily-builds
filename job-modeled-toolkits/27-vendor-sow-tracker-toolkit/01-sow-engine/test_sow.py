"""Tests for the vendor SOW earned-value engine.

Covers the per-entry cost, earned value, CPI, the estimate at completion, the
holdback, the status labels, the end-to-end run against the sample files, and the
validation rules.

Run from this folder:
  python -m unittest
"""

import unittest
from decimal import Decimal

from cli import load_effort, load_milestones
from sow import (
    build_timeline,
    cost_performance_index,
    earned_value,
    effort_cost,
    estimate_at_completion,
    milestone_summary,
    status_for,
)
from validation import (
    ValidationError,
    validate_effort_row,
    validate_holdback_rate,
    validate_milestone_row,
)

HOLDBACK = Decimal("0.10")


def D(value):
    return Decimal(value)


class UnitMathTests(unittest.TestCase):
    def test_effort_cost(self):
        self.assertEqual(effort_cost(D("140"), D("150")), D("21000.00"))

    def test_cpi(self):
        self.assertEqual(cost_performance_index(D("50000"), D("52000")), D("0.9615"))

    def test_eac_is_budget_over_cpi(self):
        # 80,000 budget, 52,000 cost, 50,000 earned -> 83,200.00.
        self.assertEqual(estimate_at_completion(D("80000"), D("52000"), D("50000")), D("83200.00"))

    def test_status_labels(self):
        self.assertEqual(status_for(D("80000"), D("85000")), "Over budget")
        self.assertEqual(status_for(D("80000"), D("83200")), "At risk")
        self.assertEqual(status_for(D("80000"), D("79000")), "On track")


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.milestones = load_milestones("milestones.csv")
        self.effort = load_effort("effort_log.csv", {m["milestone_id"] for m in self.milestones})
        self.timeline = build_timeline(self.milestones, self.effort, HOLDBACK)
        self.by_week = {r["week"]: r for r in self.timeline["rows"]}

    def test_total_budget(self):
        self.assertEqual(self.timeline["total_budget"], D("80000.00"))

    def test_week_one(self):
        w = self.by_week[1]
        self.assertEqual(w["cost_to_date"], D("21000.00"))
        self.assertEqual(w["earned_value"], D("20000.00"))
        self.assertEqual(w["cpi"], D("0.9524"))
        self.assertEqual(w["eac"], D("84000.00"))
        self.assertEqual(w["vac"], D("-4000.00"))
        self.assertEqual(w["holdback_accrued"], D("2000.00"))
        self.assertEqual(w["status"], "At risk")

    def test_week_three_hand_check(self):
        w = self.by_week[3]
        self.assertEqual(w["cost_to_date"], D("52000.00"))
        self.assertEqual(w["earned_value"], D("50000.00"))
        self.assertEqual(w["eac"], D("83200.00"))
        self.assertEqual(w["vac"], D("-3200.00"))
        self.assertEqual(w["holdback_accrued"], D("5000.00"))
        self.assertEqual(w["status"], "At risk")

    def test_week_two_over_budget(self):
        w = self.by_week[2]
        self.assertEqual(w["eac"], D("84571.43"))
        self.assertEqual(w["status"], "Over budget")

    def test_final_week(self):
        w = self.by_week[5]
        self.assertEqual(w["cost_to_date"], D("85000.00"))
        self.assertEqual(w["earned_value"], D("80000.00"))
        self.assertEqual(w["percent_complete"], D("1.0000"))
        self.assertEqual(w["percent_spent"], D("1.0625"))
        self.assertEqual(w["cpi"], D("0.9412"))
        self.assertEqual(w["eac"], D("85000.00"))
        self.assertEqual(w["vac"], D("-5000.00"))
        self.assertEqual(w["holdback_released"], D("8000.00"))
        self.assertEqual(w["status"], "Over budget")

    def test_holdback_released_only_at_completion(self):
        self.assertEqual(self.by_week[4]["holdback_released"], D("0.00"))
        self.assertEqual(self.by_week[5]["holdback_released"], D("8000.00"))


class MilestoneSummaryTests(unittest.TestCase):
    def setUp(self):
        self.milestones = load_milestones("milestones.csv")
        self.effort = load_effort("effort_log.csv", {m["milestone_id"] for m in self.milestones})
        self.summary = {r["milestone_id"]: r for r in milestone_summary(self.milestones, self.effort)}

    def test_over_budget_milestone(self):
        m = self.summary["M1"]
        self.assertEqual(m["actual_cost"], D("21000.00"))
        self.assertEqual(m["variance"], D("-1000.00"))
        self.assertEqual(m["status"], "Over budget")

    def test_on_budget_milestone(self):
        m = self.summary["M3"]
        self.assertEqual(m["variance"], D("0.00"))
        self.assertEqual(m["status"], "On budget")

    def test_totals_tie(self):
        actual = sum(r["actual_cost"] for r in self.summary.values())
        budget = sum(r["budget"] for r in self.summary.values())
        self.assertEqual(actual, D("85000.00"))
        self.assertEqual(budget, D("80000.00"))


class ValidationTests(unittest.TestCase):
    def test_unknown_milestone_rejected(self):
        with self.assertRaises(ValidationError):
            validate_effort_row(
                {"week": "1", "milestone_id": "M9", "hours": "10", "rate": "100"}, {"M1"})

    def test_zero_budget_rejected(self):
        with self.assertRaises(ValidationError):
            validate_milestone_row(
                {"milestone_id": "M1", "name": "x", "budget": "0", "complete_week": "1"})

    def test_holdback_above_one_rejected(self):
        with self.assertRaises(ValidationError):
            validate_holdback_rate("1.5")

    def test_negative_hours_rejected(self):
        with self.assertRaises(ValidationError):
            validate_effort_row(
                {"week": "1", "milestone_id": "M1", "hours": "-5", "rate": "100"}, {"M1"})

    def test_invalid_effort_file_rejected(self):
        milestones = load_milestones("milestones.csv")
        with self.assertRaises(ValidationError):
            load_effort("effort_invalid.csv", {m["milestone_id"] for m in milestones})


if __name__ == "__main__":
    unittest.main()
