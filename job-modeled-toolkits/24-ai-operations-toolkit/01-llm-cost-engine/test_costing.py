"""Tests for the LLM cost engine.

Covers the per-call cost math, the largest-remainder allocation, the run-rate
forecast, the budget labels, the end-to-end run against the sample files, and
every validation rule.

Run from this folder:
  python -m unittest
"""

import unittest
from datetime import date
from decimal import Decimal

from cli import load_budgets, load_price_book, load_shared, load_usage
from costing import (
    allocate_largest_remainder,
    budget_status,
    call_cost,
    forecast_direct,
    summarize,
    utilization_pct,
)
from validation import (
    ValidationError,
    validate_budget_row,
    validate_price_row,
    validate_shared_row,
    validate_usage_row,
)


def D(value):
    return Decimal(value)


PRICES = {
    "frontier-large": {
        "input_per_1m": D("5.00"), "cached_input_per_1m": D("0.50"), "output_per_1m": D("15.00"),
    },
    "frontier-mini": {
        "input_per_1m": D("0.15"), "cached_input_per_1m": D("0.015"), "output_per_1m": D("0.60"),
    },
    "open-8b-self": {
        "input_per_1m": D("0.05"), "cached_input_per_1m": D("0.00"), "output_per_1m": D("0.10"),
    },
}


class CallCostTests(unittest.TestCase):
    def test_clean_frontier_large(self):
        # 30M uncached x 5 + 10M cached x 0.50 + 8M out x 15 = 275.00
        cost = call_cost(40_000_000, 8_000_000, 10_000_000, PRICES["frontier-large"])
        self.assertEqual(cost, D("275.00"))

    def test_half_cent_rounds_up(self):
        # 25M x 0.15 + 25M x 0.015 + 10M x 0.60 = 10.125 -> 10.13
        cost = call_cost(50_000_000, 10_000_000, 25_000_000, PRICES["frontier-mini"])
        self.assertEqual(cost, D("10.13"))

    def test_fully_cached_prompt(self):
        # 0 uncached + 5M cached x 0.015 + 0.5M out x 0.60 = 0.375 -> 0.38
        cost = call_cost(5_000_000, 500_000, 5_000_000, PRICES["frontier-mini"])
        self.assertEqual(cost, D("0.38"))

    def test_zero_output_request(self):
        cost = call_cost(6_000_000, 0, 0, PRICES["frontier-mini"])
        self.assertEqual(cost, D("0.90"))

    def test_self_hosted_no_cached_rate(self):
        cost = call_cost(100_000_000, 20_000_000, 0, PRICES["open-8b-self"])
        self.assertEqual(cost, D("7.00"))


class AllocationTests(unittest.TestCase):
    def test_parts_sum_to_pool(self):
        weights = {"A": D("549.10"), "B": D("66.19"), "C": D("35.06"), "D": D("125.50")}
        shares = allocate_largest_remainder(D("840.00"), weights)
        self.assertEqual(sum(shares.values()), D("840.00"))

    def test_known_largest_remainder_split(self):
        weights = {
            "Engineering": D("549.10"), "Sales": D("66.19"),
            "Support": D("35.06"), "DataScience": D("125.50"),
        }
        shares = allocate_largest_remainder(D("840.00"), weights)
        self.assertEqual(shares["Engineering"], D("594.50"))
        self.assertEqual(shares["Sales"], D("71.66"))
        self.assertEqual(shares["Support"], D("37.96"))
        self.assertEqual(shares["DataScience"], D("135.88"))

    def test_zero_weight_team_gets_nothing(self):
        shares = allocate_largest_remainder(D("100.00"), {"A": D("100.00"), "B": D("0.00")})
        self.assertEqual(shares["B"], D("0.00"))
        self.assertEqual(shares["A"], D("100.00"))

    def test_all_zero_weights_split_evenly(self):
        shares = allocate_largest_remainder(D("10.00"), {"A": D("0"), "B": D("0")})
        self.assertEqual(sum(shares.values()), D("10.00"))
        self.assertEqual(shares["A"], D("5.00"))
        self.assertEqual(shares["B"], D("5.00"))


class ForecastAndStatusTests(unittest.TestCase):
    def test_run_rate_forecast(self):
        # 549.10 over 20 days -> 27.455 per day -> x30 = 823.65
        self.assertEqual(forecast_direct(D("549.10"), date(2026, 6, 20)), D("823.65"))

    def test_budget_status_labels(self):
        self.assertEqual(budget_status(D("1143.60"), D("1000.00")), "Over budget")
        self.assertEqual(budget_status(D("137.85"), D("150.00")), "Near limit")
        self.assertEqual(budget_status(D("73.02"), D("200.00")), "Within budget")

    def test_utilization(self):
        self.assertEqual(utilization_pct(D("1143.60"), D("1000.00")), D("114.4"))
        self.assertEqual(utilization_pct(D("137.85"), D("150.00")), D("91.9"))


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.prices = load_price_book("price_book.csv")
        self.budgets = load_budgets("budgets.csv")
        self.shared_total, _ = load_shared("shared_costs.csv")
        self.usage = load_usage("usage_log.csv", set(self.prices), self.budgets)
        self.result = summarize(
            self.usage, self.prices, self.shared_total, self.budgets, date(2026, 6, 20)
        )
        self.by_team = {row["team"]: row for row in self.result["per_team"]}

    def test_direct_cost_by_team(self):
        self.assertEqual(self.by_team["Engineering"]["direct_cost"], D("549.10"))
        self.assertEqual(self.by_team["Sales"]["direct_cost"], D("66.19"))
        self.assertEqual(self.by_team["Support"]["direct_cost"], D("35.06"))
        self.assertEqual(self.by_team["DataScience"]["direct_cost"], D("125.50"))

    def test_allocated_shared_sums_to_pool(self):
        allocated = sum(t["allocated_shared"] for t in self.result["per_team"])
        self.assertEqual(allocated, D("840.00"))

    def test_loaded_cost_and_status(self):
        eng = self.by_team["Engineering"]
        self.assertEqual(eng["loaded_cost"], D("1143.60"))
        self.assertEqual(eng["status"], "Over budget")
        sales = self.by_team["Sales"]
        self.assertEqual(sales["loaded_cost"], D("137.85"))
        self.assertEqual(sales["status"], "Near limit")
        self.assertEqual(self.by_team["Support"]["status"], "Within budget")
        self.assertEqual(self.by_team["DataScience"]["status"], "Within budget")

    def test_grand_totals(self):
        totals = self.result["totals"]
        self.assertEqual(totals["direct_cost"], D("775.85"))
        self.assertEqual(totals["allocated_shared"], D("840.00"))
        self.assertEqual(totals["loaded_cost"], D("1615.85"))

    def test_forecast_crosses_budget_for_sales(self):
        sales = self.by_team["Sales"]
        self.assertEqual(sales["forecast_loaded"], D("170.95"))
        self.assertEqual(sales["forecast_status"], "Over budget")

    def test_per_call_total_matches_direct_grand_total(self):
        # This is the figure the SQL reconciliation re-sums and confirms.
        per_call_total = sum(c["cost"] for c in self.result["per_call"])
        self.assertEqual(per_call_total, D("775.85"))

    def test_model_rollup_present_for_every_model(self):
        models = {row["model"] for row in self.result["per_model"]}
        self.assertEqual(models, {"frontier-large", "balanced-mid", "frontier-mini", "open-8b-self"})


class ValidationTests(unittest.TestCase):
    def _usage(self, **overrides):
        base = {
            "record_id": "U-1", "usage_date": "2026-06-01", "team": "Sales",
            "project": "p", "model": "frontier-mini", "requests": "10",
            "input_tokens": "1000", "cached_input_tokens": "0", "output_tokens": "500",
        }
        base.update(overrides)
        return base

    def test_clean_usage_parses(self):
        parsed = validate_usage_row(self._usage(), {"frontier-mini"})
        self.assertEqual(parsed["input_tokens"], 1000)
        self.assertEqual(parsed["usage_date"], date(2026, 6, 1))

    def test_unknown_model_rejected(self):
        with self.assertRaises(ValidationError):
            validate_usage_row(self._usage(model="mystery-model"), {"frontier-mini"})

    def test_negative_tokens_rejected(self):
        with self.assertRaises(ValidationError):
            validate_usage_row(self._usage(input_tokens="-5"), {"frontier-mini"})

    def test_cached_above_input_rejected(self):
        with self.assertRaises(ValidationError):
            validate_usage_row(
                self._usage(input_tokens="100", cached_input_tokens="200"), {"frontier-mini"}
            )

    def test_bad_date_rejected(self):
        with self.assertRaises(ValidationError):
            validate_usage_row(self._usage(usage_date="06/01/2026"), {"frontier-mini"})

    def test_missing_field_rejected(self):
        with self.assertRaises(ValidationError):
            validate_usage_row(self._usage(team=""), {"frontier-mini"})

    def test_non_integer_tokens_rejected(self):
        with self.assertRaises(ValidationError):
            validate_usage_row(self._usage(output_tokens="1.5"), {"frontier-mini"})

    def test_price_negative_rejected(self):
        with self.assertRaises(ValidationError):
            validate_price_row({
                "model": "x", "input_per_1m": "-1", "cached_input_per_1m": "0", "output_per_1m": "1",
            })

    def test_budget_zero_rejected(self):
        with self.assertRaises(ValidationError):
            validate_budget_row({"team": "Sales", "monthly_budget": "0"})

    def test_shared_negative_rejected(self):
        with self.assertRaises(ValidationError):
            validate_shared_row({"item": "fee", "amount": "-5"})


if __name__ == "__main__":
    unittest.main()
