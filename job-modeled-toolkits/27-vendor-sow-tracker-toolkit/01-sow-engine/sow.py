"""Earned-value logic for a vendor statement-of-work (SOW) tracker.

Pure functions only. Each takes plain values and returns plain values, with no
file or console access. The CLI layer in cli.py reads the files and writes the
timeline; the browser view in 02 reads that timeline.

The model walks the SOW week by week and, at each week, measures the work earned
against the money spent the way a vendor manager would:

  Earned value   - the budget of every milestone complete by that week.
  Cost to date   - the effort logged so far, hours times rate.
  CPI            - earned value over cost to date. Below 1 means the work is
                   costing more than it is worth.
  EAC            - estimate at completion, the total budget divided by CPI, which
                   is what the whole SOW looks set to cost at the current pace.
  VAC            - variance at completion, budget minus EAC. Negative is an overrun.
  Holdback       - a share of earned value retained until the SOW is complete,
                   then released.

All money is decimal.Decimal rounded half up to the cent.
"""

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
RATIO = Decimal("0.0001")

AT_RISK_OVER = Decimal("1.00")   # EAC above budget at all
OVER_BUDGET_OVER = Decimal("1.05")  # EAC more than five percent above budget


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def ratio(value):
    return value.quantize(RATIO, rounding=ROUND_HALF_UP)


def effort_cost(hours, rate):
    """Cost of one effort entry: hours times the billing rate."""
    return money(Decimal(hours) * rate)


def earned_value(milestones, week):
    """Budget of every milestone complete by the given week."""
    return money(sum(
        (m["budget"] for m in milestones if m["complete_week"] <= week),
        Decimal("0.00"),
    ))


def cost_performance_index(earned, cost_to_date):
    """Earned value over cost to date. Zero cost returns 0 for a clean start."""
    if cost_to_date <= 0:
        return Decimal("0.0000")
    return ratio(earned / cost_to_date)


def estimate_at_completion(total_budget, cost_to_date, earned):
    """What the SOW looks set to cost at the current pace: budget divided by CPI,
    computed as budget times cost over earned so the cents are exact."""
    if earned <= 0:
        return money(total_budget)
    return money(total_budget * cost_to_date / earned)


def variance_at_completion(total_budget, eac):
    """Budget minus the estimate at completion. Negative is an overrun."""
    return money(total_budget - eac)


def holdback_accrued(holdback_rate, earned):
    """The share of earned value held back so far."""
    return money(holdback_rate * earned)


def status_for(total_budget, eac):
    """Label the SOW from its estimate at completion against budget."""
    if eac > money(total_budget * OVER_BUDGET_OVER):
        return "Over budget"
    if eac > total_budget:
        return "At risk"
    return "On track"


def total_budget_of(milestones):
    return money(sum((m["budget"] for m in milestones), Decimal("0.00")))


def build_timeline(milestones, effort, holdback_rate):
    """Build the week-by-week earned-value timeline.

    milestones is a list of validated dicts with a Decimal budget and an integer
    complete_week. effort is a list of validated dicts with an integer week, a
    Decimal hours, and a Decimal rate. Returns a list of one row per week from 1
    to the last week with effort.
    """
    total_budget = total_budget_of(milestones)
    last_week = max([e["week"] for e in effort] + [m["complete_week"] for m in milestones])

    rows = []
    for week in range(1, last_week + 1):
        cost_to_date = money(sum(
            (effort_cost(e["hours"], e["rate"]) for e in effort if e["week"] <= week),
            Decimal("0.00"),
        ))
        earned = earned_value(milestones, week)
        eac = estimate_at_completion(total_budget, cost_to_date, earned)
        complete = earned >= total_budget
        accrued = holdback_accrued(holdback_rate, earned)
        rows.append({
            "week": week,
            "cost_to_date": cost_to_date,
            "earned_value": earned,
            "percent_complete": ratio(earned / total_budget) if total_budget > 0 else Decimal("0.0000"),
            "percent_spent": ratio(cost_to_date / total_budget) if total_budget > 0 else Decimal("0.0000"),
            "cpi": cost_performance_index(earned, cost_to_date),
            "eac": eac,
            "vac": variance_at_completion(total_budget, eac),
            "holdback_accrued": accrued,
            "holdback_released": accrued if complete else Decimal("0.00"),
            "status": status_for(total_budget, eac),
            "complete": complete,
        })
    return {"total_budget": total_budget, "rows": rows}


def milestone_summary(milestones, effort):
    """Per-milestone budget, actual cost, and variance."""
    rows = []
    for m in sorted(milestones, key=lambda x: x["complete_week"]):
        actual = money(sum(
            (effort_cost(e["hours"], e["rate"]) for e in effort if e["milestone_id"] == m["milestone_id"]),
            Decimal("0.00"),
        ))
        variance = money(m["budget"] - actual)
        rows.append({
            "milestone_id": m["milestone_id"],
            "name": m["name"],
            "budget": money(m["budget"]),
            "actual_cost": actual,
            "variance": variance,
            "percent_spent": ratio(actual / m["budget"]) if m["budget"] > 0 else Decimal("0.0000"),
            "status": "Over budget" if variance < 0 else ("On budget" if variance == 0 else "Under budget"),
        })
    return rows
