"""Tests for the construction WIP and job-cost engine.

Covers the percent-complete and earned-revenue math, the over/under billing
position, the status labels, the end-to-end run against the sample contracts,
and every validation rule.

Run from this folder:
  python -m unittest
"""

import unittest
from decimal import Decimal

from cli import load_contracts
from validation import ValidationError, validate_contract_row
from wip import (
    billing_status,
    cost_to_complete,
    earned_revenue,
    estimated_gross_profit,
    gross_profit_to_date,
    over_under_billing,
    percent_complete,
    summarize,
)


def D(value):
    return Decimal(value)


class PercentCompleteTests(unittest.TestCase):
    def test_sixty_percent(self):
        self.assertEqual(percent_complete(D("480000"), D("800000")), D("0.6000"))

    def test_not_started_is_zero(self):
        self.assertEqual(percent_complete(D("0"), D("420000")), D("0.0000"))

    def test_complete_is_one(self):
        self.assertEqual(percent_complete(D("200000"), D("200000")), D("1.0000"))

    def test_repeating_ratio_rounds_to_four_places(self):
        self.assertEqual(percent_complete(D("1"), D("3")), D("0.3333"))
        self.assertEqual(percent_complete(D("2"), D("3")), D("0.6667"))


class EarnedRevenueTests(unittest.TestCase):
    def test_hand_checked_job(self):
        # 1,200,000 contract at 60% complete earns 720,000.00.
        self.assertEqual(earned_revenue(D("1200000"), D("480000"), D("800000")), D("720000.00"))

    def test_half_cent_rounds_up(self):
        # 10,000.05 * 1 / 2 = 5,000.025 -> 5,000.03 half up.
        self.assertEqual(earned_revenue(D("10000.05"), D("1"), D("2")), D("5000.03"))

    def test_quarter_progress(self):
        self.assertEqual(earned_revenue(D("380000"), D("351000"), D("360000")), D("370500.00"))


class BillingPositionTests(unittest.TestCase):
    def test_underbilled_is_positive(self):
        self.assertEqual(over_under_billing(D("720000.00"), D("700000.00")), D("20000.00"))
        self.assertEqual(billing_status(D("20000.00")), "Underbilled")

    def test_overbilled_is_negative(self):
        self.assertEqual(over_under_billing(D("100000.00"), D("150000.00")), D("-50000.00"))
        self.assertEqual(billing_status(D("-50000.00")), "Overbilled")

    def test_even_position(self):
        self.assertEqual(over_under_billing(D("250000.00"), D("250000.00")), D("0.00"))
        self.assertEqual(billing_status(D("0.00")), "Even")


class ProfitTests(unittest.TestCase):
    def test_cost_to_complete(self):
        self.assertEqual(cost_to_complete(D("800000"), D("480000")), D("320000.00"))

    def test_estimated_gross_profit(self):
        self.assertEqual(estimated_gross_profit(D("1200000"), D("800000")), D("400000.00"))

    def test_gross_profit_to_date(self):
        self.assertEqual(gross_profit_to_date(D("720000.00"), D("480000")), D("240000.00"))


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.contracts = load_contracts("contracts.csv")
        self.result = summarize(self.contracts)
        self.by_job = {row["job_id"]: row for row in self.result["per_job"]}

    def test_hand_checked_job_full_row(self):
        job = self.by_job["J-1001"]
        self.assertEqual(job["percent_complete"], D("0.6000"))
        self.assertEqual(job["earned_revenue"], D("720000.00"))
        self.assertEqual(job["over_under_billing"], D("20000.00"))
        self.assertEqual(job["status"], "Underbilled")

    def test_each_status_present(self):
        self.assertEqual(self.by_job["J-1002"]["status"], "Overbilled")
        self.assertEqual(self.by_job["J-1003"]["status"], "Even")
        self.assertEqual(self.by_job["J-1004"]["status"], "Overbilled")
        self.assertEqual(self.by_job["J-1005"]["status"], "Underbilled")

    def test_not_started_job(self):
        job = self.by_job["J-1004"]
        self.assertEqual(job["percent_complete"], D("0.0000"))
        self.assertEqual(job["earned_revenue"], D("0.00"))
        self.assertEqual(job["over_under_billing"], D("-60000.00"))

    def test_grand_totals(self):
        totals = self.result["totals"]
        self.assertEqual(totals["contract_value"], D("5330000.00"))
        self.assertEqual(totals["estimated_total_cost"], D("3930000.00"))
        self.assertEqual(totals["cost_to_date"], D("2001000.00"))
        self.assertEqual(totals["billed_to_date"], D("2682000.00"))
        self.assertEqual(totals["earned_revenue"], D("2640500.00"))
        self.assertEqual(totals["cost_to_complete"], D("1929000.00"))
        self.assertEqual(totals["estimated_gross_profit"], D("1400000.00"))
        self.assertEqual(totals["gross_profit_to_date"], D("639500.00"))
        self.assertEqual(totals["over_under_billing"], D("-41500.00"))

    def test_status_counts(self):
        totals = self.result["totals"]
        self.assertEqual(totals["underbilled_count"], 2)
        self.assertEqual(totals["overbilled_count"], 3)
        self.assertEqual(totals["even_count"], 1)

    def test_over_under_ties_to_earned_minus_billed(self):
        # The figure the workbook re-derives with its own formulas.
        totals = self.result["totals"]
        self.assertEqual(
            totals["over_under_billing"],
            totals["earned_revenue"] - totals["billed_to_date"],
        )


class ValidationTests(unittest.TestCase):
    def _contract(self, **overrides):
        base = {
            "job_id": "J-1", "job_name": "Test Job", "contract_value": "100000",
            "estimated_total_cost": "80000", "cost_to_date": "40000",
            "billed_to_date": "50000",
        }
        base.update(overrides)
        return base

    def test_clean_contract_parses(self):
        parsed = validate_contract_row(self._contract())
        self.assertEqual(parsed["contract_value"], D("100000"))
        self.assertEqual(parsed["job_name"], "Test Job")

    def test_cost_above_estimate_rejected(self):
        with self.assertRaises(ValidationError):
            validate_contract_row(self._contract(cost_to_date="90000"))

    def test_zero_contract_value_rejected(self):
        with self.assertRaises(ValidationError):
            validate_contract_row(self._contract(contract_value="0"))

    def test_zero_estimate_rejected(self):
        with self.assertRaises(ValidationError):
            validate_contract_row(self._contract(estimated_total_cost="0"))

    def test_negative_billed_rejected(self):
        with self.assertRaises(ValidationError):
            validate_contract_row(self._contract(billed_to_date="-1"))

    def test_non_numeric_amount_rejected(self):
        with self.assertRaises(ValidationError):
            validate_contract_row(self._contract(cost_to_date="forty thousand"))

    def test_missing_field_rejected(self):
        with self.assertRaises(ValidationError):
            validate_contract_row(self._contract(job_name=""))

    def test_invalid_sample_file_rejected(self):
        with self.assertRaises(ValidationError):
            load_contracts("contracts_invalid.csv")


if __name__ == "__main__":
    unittest.main()
