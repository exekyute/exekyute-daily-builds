"""Grant drawdown and compliance logic.

Pure functions only. Each takes plain values and returns plain values, with no
file or console access. The CLI layer in cli.py reads the files and writes the
timeline; the browser view in 02 reads that timeline.

The model walks a grant period by period and, at each period, tracks how much of
the award has been drawn down on allowable costs, the run-rate burn, the runway
left, and where the spend is heading by the award end. A cost is allowable only if
its category is one the award budgets; anything else is disallowed and kept out of
the drawdown. It also tracks which reports are overdue.

All money is decimal.Decimal rounded half up to the cent.
"""

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def is_allowable(category, budget_categories):
    """A cost is allowable only against a category the award budgets."""
    return category in budget_categories


def burn_rate(cumulative_allowable, period):
    """Average allowable spend per period so far."""
    if period <= 0:
        return Decimal("0.00")
    return money(cumulative_allowable / Decimal(period))


def projected_total(cumulative_allowable, period, award_months):
    """Where allowable spend lands by the award end at the current run rate.

    Computed in one step from the cumulative spend so the cents are exact:
    cumulative times award months over periods elapsed.
    """
    if period <= 0:
        return Decimal("0.00")
    return money(cumulative_allowable * Decimal(award_months) / Decimal(period))


def runway_periods(remaining, rate):
    """How many more periods the remaining award lasts at the current rate."""
    if rate <= 0:
        return None
    return (remaining / rate).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def reports_overdue(deadlines, period):
    """Reports whose due period has passed and that are not submitted."""
    return [d for d in deadlines if d["due_period"] <= period and not d["submitted"]]


def build_timeline(transactions, budget_categories, award_total, award_months, as_of, deadlines):
    """Build the period-by-period drawdown timeline up to the as-of period."""
    rows = []
    for period in range(1, as_of + 1):
        allowable = money(sum(
            (t["amount"] for t in transactions
             if t["period"] <= period and is_allowable(t["category"], budget_categories)),
            Decimal("0.00"),
        ))
        disallowed = money(sum(
            (t["amount"] for t in transactions
             if t["period"] <= period and not is_allowable(t["category"], budget_categories)),
            Decimal("0.00"),
        ))
        rate = burn_rate(allowable, period)
        projected = projected_total(allowable, period, award_months)
        overdue = reports_overdue(deadlines, period)
        rows.append({
            "period": period,
            "cumulative_allowable": allowable,
            "cumulative_disallowed": disallowed,
            "burn_rate": rate,
            "remaining": money(award_total - allowable),
            "projected_total": projected,
            "projected_variance": money(award_total - projected),
            "status": "Over budget" if projected > award_total else "On track",
            "reports_overdue": len(overdue),
        })
    return rows


def category_summary(transactions, budgets, budget_categories):
    """Per-category budget, allowable spend, remaining, and status."""
    rows = []
    for category in sorted(budgets):
        spent = money(sum(
            (t["amount"] for t in transactions
             if t["category"] == category and is_allowable(category, budget_categories)),
            Decimal("0.00"),
        ))
        budget = money(budgets[category])
        rows.append({
            "category": category,
            "budget": budget,
            "spent": spent,
            "remaining": money(budget - spent),
            "status": "Over budget" if spent > budget else "Within budget",
        })
    return rows


def deadline_status(deadlines, as_of):
    """Status of every report as of the current period."""
    rows = []
    for d in sorted(deadlines, key=lambda x: x["due_period"]):
        if d["submitted"]:
            status = "Submitted"
        elif d["due_period"] < as_of:
            status = "Overdue"
        elif d["due_period"] == as_of:
            status = "Due now"
        else:
            status = "Upcoming"
        rows.append({
            "report": d["report"], "due_period": d["due_period"],
            "submitted": "yes" if d["submitted"] else "no", "status": status,
        })
    return rows
