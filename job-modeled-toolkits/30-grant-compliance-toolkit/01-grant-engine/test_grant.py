"""Tests for the grant drawdown and compliance engine.

Covers the allowable check, the burn rate and projection, the runway, the overdue
report count, the end-to-end run against the sample files, and the validation rules.

Run from this folder:
  python -m unittest
"""

import unittest
from decimal import Decimal

from cli import load_award, load_deadlines, load_transactions
from grant import (
    build_timeline,
    burn_rate,
    category_summary,
    deadline_status,
    is_allowable,
    projected_total,
    runway_periods,
)
from validation import ValidationError, validate_txn_row


def D(value):
    return Decimal(value)


CATEGORIES = {"Salaries", "Equipment", "Travel", "Indirect"}


class UnitTests(unittest.TestCase):
    def test_allowable_category(self):
        self.assertTrue(is_allowable("Salaries", CATEGORIES))
        self.assertFalse(is_allowable("Entertainment", CATEGORIES))

    def test_burn_rate(self):
        self.assertEqual(burn_rate(D("100000"), 4), D("25000.00"))

    def test_projection_is_exact(self):
        self.assertEqual(projected_total(D("100000"), 4, 12), D("300000.00"))
        self.assertEqual(projected_total(D("76000"), 3, 12), D("304000.00"))

    def test_runway(self):
        self.assertEqual(runway_periods(D("150000"), D("25000")), D("6.0"))


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.budgets = load_award("award.csv")
        self.txns = load_transactions("transactions.csv")
        self.deadlines = load_deadlines("reporting_schedule.csv")
        self.award_total = sum(self.budgets.values())
        self.timeline = build_timeline(self.txns, set(self.budgets), self.award_total, 12, 4, self.deadlines)
        self.by_period = {r["period"]: r for r in self.timeline}

    def test_award_total(self):
        self.assertEqual(self.award_total, D("250000"))

    def test_period_one_on_track(self):
        p = self.by_period[1]
        self.assertEqual(p["cumulative_allowable"], D("16000.00"))
        self.assertEqual(p["projected_total"], D("192000.00"))
        self.assertEqual(p["status"], "On track")

    def test_disallowed_appears_in_period_two(self):
        p = self.by_period[2]
        self.assertEqual(p["cumulative_disallowed"], D("5000.00"))
        self.assertEqual(p["status"], "Over budget")

    def test_final_period_hand_check(self):
        p = self.by_period[4]
        self.assertEqual(p["cumulative_allowable"], D("100000.00"))
        self.assertEqual(p["cumulative_disallowed"], D("5000.00"))
        self.assertEqual(p["remaining"], D("150000.00"))
        self.assertEqual(p["burn_rate"], D("25000.00"))
        self.assertEqual(p["projected_total"], D("300000.00"))
        self.assertEqual(p["projected_variance"], D("-50000.00"))
        self.assertEqual(p["status"], "Over budget")
        self.assertEqual(p["reports_overdue"], 1)

    def test_category_summary(self):
        summary = {r["category"]: r for r in category_summary(self.txns, self.budgets, set(self.budgets))}
        self.assertEqual(summary["Salaries"]["spent"], D("80000.00"))
        self.assertEqual(summary["Equipment"]["spent"], D("12000.00"))
        self.assertEqual(summary["Travel"]["spent"], D("5000.00"))
        self.assertEqual(summary["Indirect"]["spent"], D("3000.00"))
        self.assertTrue(all(r["status"] == "Within budget" for r in summary.values()))

    def test_deadline_status(self):
        statuses = {r["report"]: r["status"] for r in deadline_status(self.deadlines, 4)}
        self.assertEqual(statuses["Q1 financial report"], "Overdue")
        self.assertEqual(statuses["Mid-term report"], "Upcoming")
        self.assertEqual(statuses["Final report"], "Upcoming")


class ValidationTests(unittest.TestCase):
    def test_zero_period_rejected(self):
        with self.assertRaises(ValidationError):
            validate_txn_row({"period": "0", "category": "Salaries", "amount": "100"})

    def test_negative_amount_rejected(self):
        with self.assertRaises(ValidationError):
            validate_txn_row({"period": "1", "category": "Salaries", "amount": "-5"})

    def test_invalid_transactions_file_rejected(self):
        with self.assertRaises(ValidationError):
            load_transactions("transactions_invalid.csv")


if __name__ == "__main__":
    unittest.main()
