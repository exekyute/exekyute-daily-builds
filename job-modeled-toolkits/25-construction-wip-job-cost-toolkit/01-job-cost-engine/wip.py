"""Work-in-progress (WIP) and job-cost logic for a construction schedule.

Pure functions only. Each takes plain values and returns plain values, with no
file or console access. The CLI layer in cli.py does all the reading and writing.

The method here is cost-to-cost percent complete, the common way a contractor
recognizes revenue on a long job:

  Percent complete = cost to date / estimated total cost.
  Earned revenue   = contract value * percent complete.
  Over/under billing = earned revenue - billed to date. A job that has earned
                       more than it has billed is underbilled (an asset, costs
                       and estimated earnings in excess of billings). A job that
                       has billed more than it has earned is overbilled (a
                       liability, billings in excess of costs and earnings).
  Gross profit to date = earned revenue - cost to date.
  Estimated gross profit at completion = contract value - estimated total cost.

All money is decimal.Decimal rounded half up to the cent, so the figures match
the workbook formulas the next tool writes, to the cent.
"""

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
RATIO = Decimal("0.0001")


def money(value):
    """Round a Decimal to the cent, half up. Keeps every figure fixed-point."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def ratio(value):
    """Round a percent-complete ratio to four decimal places, half up."""
    return value.quantize(RATIO, rounding=ROUND_HALF_UP)


def percent_complete(cost_to_date, estimated_total_cost):
    """Cost-to-cost percent complete as a ratio between 0 and 1.

    estimated_total_cost is greater than zero (the validation layer enforces it)
    and is never less than cost_to_date, so the ratio stays within 0 and 1.
    """
    return ratio(cost_to_date / estimated_total_cost)


def earned_revenue(contract_value, cost_to_date, estimated_total_cost):
    """Revenue earned to date: contract value times percent complete.

    Computed from the raw inputs in one step, then rounded to the cent, so the
    rounding matches the workbook's =ROUND(contract*cost/estimate, 2) formula.
    """
    return money(contract_value * cost_to_date / estimated_total_cost)


def cost_to_complete(estimated_total_cost, cost_to_date):
    """Cost still expected on the job: estimate minus what has been spent."""
    return money(estimated_total_cost - cost_to_date)


def estimated_gross_profit(contract_value, estimated_total_cost):
    """Gross profit the whole job is expected to make: price minus total cost."""
    return money(contract_value - estimated_total_cost)


def gross_profit_to_date(earned, cost_to_date):
    """Gross profit recognized so far: earned revenue minus cost to date."""
    return money(earned - cost_to_date)


def over_under_billing(earned, billed_to_date):
    """Earned revenue minus billings. Positive is underbilled, negative is over."""
    return money(earned - billed_to_date)


def billing_status(over_under):
    """Label a job from its over/under figure."""
    if over_under > 0:
        return "Underbilled"
    if over_under < 0:
        return "Overbilled"
    return "Even"


def job_row(contract):
    """Build the full result row for one validated contract.

    contract is a dict with Decimal contract_value, estimated_total_cost,
    cost_to_date, and billed_to_date, plus the string job_id and job_name.
    """
    pct = percent_complete(contract["cost_to_date"], contract["estimated_total_cost"])
    earned = earned_revenue(
        contract["contract_value"],
        contract["cost_to_date"],
        contract["estimated_total_cost"],
    )
    over_under = over_under_billing(earned, contract["billed_to_date"])
    return {
        "job_id": contract["job_id"],
        "job_name": contract["job_name"],
        "contract_value": money(contract["contract_value"]),
        "estimated_total_cost": money(contract["estimated_total_cost"]),
        "cost_to_date": money(contract["cost_to_date"]),
        "billed_to_date": money(contract["billed_to_date"]),
        "percent_complete": pct,
        "earned_revenue": earned,
        "cost_to_complete": cost_to_complete(
            contract["estimated_total_cost"], contract["cost_to_date"]
        ),
        "estimated_gross_profit": estimated_gross_profit(
            contract["contract_value"], contract["estimated_total_cost"]
        ),
        "gross_profit_to_date": gross_profit_to_date(earned, contract["cost_to_date"]),
        "over_under_billing": over_under,
        "status": billing_status(over_under),
    }


def summarize(contracts):
    """Build the per-job rows and the schedule totals from validated contracts."""
    per_job = [job_row(c) for c in contracts]

    def total(field):
        return money(sum((row[field] for row in per_job), Decimal("0.00")))

    totals = {
        "contract_value": total("contract_value"),
        "estimated_total_cost": total("estimated_total_cost"),
        "cost_to_date": total("cost_to_date"),
        "billed_to_date": total("billed_to_date"),
        "earned_revenue": total("earned_revenue"),
        "cost_to_complete": total("cost_to_complete"),
        "estimated_gross_profit": total("estimated_gross_profit"),
        "gross_profit_to_date": total("gross_profit_to_date"),
        "over_under_billing": total("over_under_billing"),
        "underbilled_count": sum(1 for r in per_job if r["status"] == "Underbilled"),
        "overbilled_count": sum(1 for r in per_job if r["status"] == "Overbilled"),
        "even_count": sum(1 for r in per_job if r["status"] == "Even"),
    }
    return {"per_job": per_job, "totals": totals}
