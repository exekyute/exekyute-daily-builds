"""Cost logic for the LLM cost engine.

Pure functions only. Each takes plain values and returns plain values, with no
file or console access. The CLI layer in cli.py does all the reading and writing.

What it computes, in order:

  Per-call cost   - billable token cost for one usage record, from the price book.
  Team rollup     - direct cost, requests, and tokens summed by team.
  Shared cost     - one monthly pool (platform fee and the like) split across teams
                    in proportion to their direct cost, using the largest-remainder
                    method so the parts sum to the pool exactly, with no cent lost.
  Loaded cost     - direct cost plus the team's allocated share of the pool.
  Budget status   - loaded cost against each team's monthly budget.
  Forecast        - month-end direct spend by straight run rate, plus the fixed pool.

All money is decimal.Decimal rounded half up to the cent, so the figures match the
SQL reconciliation and the browser dashboard exactly.
"""

import calendar
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")

# A team at or above this share of its budget is called out as near the limit.
NEAR_LIMIT_THRESHOLD = Decimal("0.90")

# Prices in the price book are quoted per one million tokens, the common unit.
TOKENS_PER_UNIT = Decimal("1000000")


def money(value):
    """Round a Decimal to the cent, half up. Keeps every figure fixed-point."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def call_cost(input_tokens, output_tokens, cached_input_tokens, price):
    """Billable cost of one usage record.

    Cached input tokens are the prompt tokens served from the provider's cache and
    are billed at the cached rate. The rest of the input is billed at the full input
    rate. price is a dict of Decimal rates per one million tokens.
    """
    uncached_input = input_tokens - cached_input_tokens
    exact = (
        Decimal(uncached_input) * price["input_per_1m"]
        + Decimal(cached_input_tokens) * price["cached_input_per_1m"]
        + Decimal(output_tokens) * price["output_per_1m"]
    ) / TOKENS_PER_UNIT
    return money(exact)


def allocate_largest_remainder(total, weights):
    """Split total across the keys of weights in proportion to each weight.

    Works in whole cents so the parts sum to total exactly. Each share is floored to
    the cent first, then the leftover cents are handed out one at a time to the keys
    with the largest fractional remainder, ties broken by key name so the result is
    deterministic. A key with zero weight gets zero. If every weight is zero the pool
    is split as evenly as the cents allow.
    """
    names = sorted(weights)
    total_cents = int((money(total) / CENT).to_integral_value(rounding=ROUND_HALF_UP))
    if not names or total_cents == 0:
        return {name: Decimal("0.00") for name in names}

    total_weight = sum(weights.values())
    if total_weight <= 0:
        effective = {name: Decimal("1") for name in names}
        total_weight = Decimal(len(names))
    else:
        effective = weights

    raw = {name: Decimal(total_cents) * effective[name] / total_weight for name in names}
    floor_cents = {name: int(raw[name] // 1) for name in names}
    handed_out = sum(floor_cents.values())
    remainder = total_cents - handed_out

    fractional = {name: raw[name] - floor_cents[name] for name in names}
    order = sorted(names, key=lambda name: (-fractional[name], name))
    for i in range(remainder):
        floor_cents[order[i]] += 1

    return {name: money(Decimal(floor_cents[name]) / Decimal("100")) for name in names}


def days_in_month(as_of):
    """Calendar days in the month that contains as_of (a datetime.date)."""
    return calendar.monthrange(as_of.year, as_of.month)[1]


def forecast_direct(direct_cost, as_of):
    """Project the month-end direct spend from the spend so far by straight run rate.

    Spend to date divided by the days elapsed in the month, times the days in the
    month. Days elapsed is the day-of-month of as_of, so a log that starts on the
    first of the month run-rates cleanly.
    """
    days_elapsed = as_of.day
    if days_elapsed <= 0:
        return money(direct_cost)
    rate_per_day = direct_cost / Decimal(days_elapsed)
    return money(rate_per_day * Decimal(days_in_month(as_of)))


def budget_status(loaded_cost, budget):
    """Label a team's loaded cost against its monthly budget."""
    if loaded_cost > budget:
        return "Over budget"
    if budget > 0 and (loaded_cost / budget) >= NEAR_LIMIT_THRESHOLD:
        return "Near limit"
    return "Within budget"


def utilization_pct(loaded_cost, budget):
    """Loaded cost as a percent of budget, rounded to one decimal place."""
    if budget <= 0:
        return Decimal("0.0")
    pct = loaded_cost / budget * Decimal("100")
    return pct.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def summarize(usage_rows, price_book, shared_total, budgets, as_of):
    """Build the per-call, per-model, and per-team results from validated input.

    usage_rows is a list of validated dicts with integer token fields and a
    datetime.date usage_date. price_book maps a model to its Decimal rates. budgets
    maps a team to its Decimal monthly budget and must cover every team that appears
    in usage. shared_total is the summed monthly shared pool. as_of drives the run
    rate forecast and is the latest usage date unless the caller overrides it.

    Returns a dict with per_call, per_model, per_team lists and the headline totals.
    """
    per_call = []
    for row in usage_rows:
        price = price_book[row["model"]]
        cost = call_cost(
            row["input_tokens"], row["output_tokens"], row["cached_input_tokens"], price
        )
        per_call.append({
            "record_id": row["record_id"],
            "usage_date": row["usage_date"].isoformat(),
            "team": row["team"],
            "project": row["project"],
            "model": row["model"],
            "requests": row["requests"],
            "input_tokens": row["input_tokens"],
            "cached_input_tokens": row["cached_input_tokens"],
            "output_tokens": row["output_tokens"],
            "cost": cost,
        })

    # Per-model rollup, for the dashboard's spend-by-model view.
    models = sorted({c["model"] for c in per_call})
    per_model = []
    for model in models:
        calls = [c for c in per_call if c["model"] == model]
        per_model.append({
            "model": model,
            "requests": sum(c["requests"] for c in calls),
            "input_tokens": sum(c["input_tokens"] for c in calls),
            "output_tokens": sum(c["output_tokens"] for c in calls),
            "cost": money(sum((c["cost"] for c in calls), Decimal("0.00"))),
        })

    # Every team with a budget appears, even one with no usage this period.
    teams = sorted(set(budgets) | {c["team"] for c in per_call})
    direct_by_team = {}
    for team in teams:
        calls = [c for c in per_call if c["team"] == team]
        direct_by_team[team] = money(sum((c["cost"] for c in calls), Decimal("0.00")))

    allocations = allocate_largest_remainder(shared_total, direct_by_team)

    per_team = []
    for team in teams:
        calls = [c for c in per_call if c["team"] == team]
        direct = direct_by_team[team]
        allocated = allocations[team]
        loaded = money(direct + allocated)
        budget = budgets[team]
        forecast = money(forecast_direct(direct, as_of) + allocated)
        per_team.append({
            "team": team,
            "requests": sum(c["requests"] for c in calls),
            "input_tokens": sum(c["input_tokens"] for c in calls),
            "output_tokens": sum(c["output_tokens"] for c in calls),
            "direct_cost": direct,
            "allocated_shared": allocated,
            "loaded_cost": loaded,
            "monthly_budget": money(budget),
            "remaining": money(budget - loaded),
            "utilization_pct": utilization_pct(loaded, budget),
            "status": budget_status(loaded, budget),
            "forecast_loaded": forecast,
            "forecast_status": budget_status(forecast, budget),
        })

    totals = {
        "direct_cost": money(sum((t["direct_cost"] for t in per_team), Decimal("0.00"))),
        "allocated_shared": money(sum((t["allocated_shared"] for t in per_team), Decimal("0.00"))),
        "loaded_cost": money(sum((t["loaded_cost"] for t in per_team), Decimal("0.00"))),
        "monthly_budget": money(sum((t["monthly_budget"] for t in per_team), Decimal("0.00"))),
        "forecast_loaded": money(sum((t["forecast_loaded"] for t in per_team), Decimal("0.00"))),
        "requests": sum(t["requests"] for t in per_team),
        "as_of": as_of.isoformat(),
    }

    return {
        "per_call": per_call,
        "per_model": per_model,
        "per_team": per_team,
        "totals": totals,
    }
