"""Tests for the subscription ledger.

Covers the cost and waste math, the renewal labels, the suggested action, the
end-to-end run against the sample subscriptions, and every validation rule.

Run from this folder:
  python -m unittest
"""

import unittest
from datetime import date
from decimal import Decimal

from cli import load_subs
from subscriptions import (
    action,
    monthly_cost,
    monthly_waste,
    renewal_status,
    summarize,
    utilization,
)
from validation import ValidationError, validate_sub_row

AS_OF = date(2026, 6, 30)


def D(value):
    return Decimal(value)


class CostTests(unittest.TestCase):
    def test_per_seat_monthly_cost(self):
        self.assertEqual(monthly_cost("per_seat", D("12"), 50), D("600.00"))

    def test_flat_monthly_cost_ignores_seats(self):
        self.assertEqual(monthly_cost("flat", D("300"), 10), D("300.00"))

    def test_waste_on_unused_seats(self):
        # 12 unused seats at 12.00 each is 144.00 a month.
        self.assertEqual(monthly_waste("per_seat", D("12"), 50, 38), D("144.00"))

    def test_flat_plan_has_no_waste(self):
        self.assertEqual(monthly_waste("flat", D("300"), 10, 4), D("0.00"))

    def test_utilization(self):
        self.assertEqual(utilization("per_seat", 50, 38), D("0.7600"))
        self.assertEqual(utilization("per_seat", 40, 18), D("0.4500"))
        self.assertIsNone(utilization("flat", 10, 10))


class RenewalAndActionTests(unittest.TestCase):
    def test_renewal_status_labels(self):
        self.assertEqual(renewal_status(-20), "Expired")
        self.assertEqual(renewal_status(5), "Due soon")
        self.assertEqual(renewal_status(77), "Upcoming")
        self.assertEqual(renewal_status(215), "Current")

    def test_action_auto_renew_and_underused(self):
        self.assertEqual(action("per_seat", 20, True, D("0.4500")), "Auto-renews soon, underused")

    def test_action_auto_renew_only(self):
        self.assertEqual(action("per_seat", 5, True, D("0.9167")), "Auto-renews soon")

    def test_action_underused_only(self):
        self.assertEqual(action("per_seat", 200, False, D("0.3600")), "Underused")

    def test_action_expired(self):
        self.assertEqual(action("per_seat", -20, False, D("0.3600")), "Expired, review")

    def test_action_ok(self):
        self.assertEqual(action("per_seat", 77, True, D("0.7600")), "OK")


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.subs = load_subs("subscriptions.csv")
        self.result = summarize(self.subs, AS_OF)
        self.by_id = {r["sub_id"]: r for r in self.result["per_sub"]}

    def test_hand_checked_subscription(self):
        s = self.by_id["S-01"]
        self.assertEqual(s["monthly_cost"], D("600.00"))
        self.assertEqual(s["annual_cost"], D("7200.00"))
        self.assertEqual(s["unused_seats"], 12)
        self.assertEqual(s["monthly_waste"], D("144.00"))
        self.assertEqual(s["annual_waste"], D("1728.00"))
        self.assertEqual(s["utilization"], D("0.7600"))
        self.assertEqual(s["action"], "OK")

    def test_underused_auto_renew(self):
        s = self.by_id["S-02"]
        self.assertEqual(s["monthly_cost"], D("1000.00"))
        self.assertEqual(s["monthly_waste"], D("550.00"))
        self.assertEqual(s["days_to_renewal"], 20)
        self.assertEqual(s["renewal_status"], "Due soon")
        self.assertEqual(s["action"], "Auto-renews soon, underused")

    def test_expired_subscription(self):
        s = self.by_id["S-05"]
        self.assertEqual(s["renewal_status"], "Expired")
        self.assertEqual(s["action"], "Expired, review")

    def test_flat_plan(self):
        s = self.by_id["S-03"]
        self.assertEqual(s["monthly_cost"], D("300.00"))
        self.assertEqual(s["monthly_waste"], D("0.00"))
        self.assertEqual(s["utilization"], None)

    def test_portfolio_totals(self):
        totals = self.result["totals"]
        self.assertEqual(totals["monthly_cost"], D("3675.00"))
        self.assertEqual(totals["annual_cost"], D("44100.00"))
        self.assertEqual(totals["monthly_waste"], D("984.00"))
        self.assertEqual(totals["annual_waste"], D("11808.00"))
        self.assertEqual(totals["due_soon_count"], 2)
        self.assertEqual(totals["expired_count"], 1)
        self.assertEqual(totals["underused_count"], 2)


class ValidationTests(unittest.TestCase):
    def _sub(self, **overrides):
        base = {
            "sub_id": "S-1", "vendor": "V", "plan": "P", "plan_type": "per_seat",
            "monthly_unit_cost": "10", "seats_owned": "5", "seats_used": "3",
            "renewal_date": "2026-08-01", "auto_renew": "yes",
        }
        base.update(overrides)
        return base

    def test_clean_row_parses(self):
        parsed = validate_sub_row(self._sub())
        self.assertEqual(parsed["seats_owned"], 5)
        self.assertTrue(parsed["auto_renew"])

    def test_seats_used_above_owned_rejected(self):
        with self.assertRaises(ValidationError):
            validate_sub_row(self._sub(seats_used="9"))

    def test_bad_plan_type_rejected(self):
        with self.assertRaises(ValidationError):
            validate_sub_row(self._sub(plan_type="annual"))

    def test_bad_auto_renew_rejected(self):
        with self.assertRaises(ValidationError):
            validate_sub_row(self._sub(auto_renew="maybe"))

    def test_bad_date_rejected(self):
        with self.assertRaises(ValidationError):
            validate_sub_row(self._sub(renewal_date="08/01/2026"))

    def test_zero_seats_owned_rejected(self):
        with self.assertRaises(ValidationError):
            validate_sub_row(self._sub(seats_owned="0"))

    def test_invalid_sample_file_rejected(self):
        with self.assertRaises(ValidationError):
            load_subs("subscriptions_invalid.csv")


if __name__ == "__main__":
    unittest.main()
