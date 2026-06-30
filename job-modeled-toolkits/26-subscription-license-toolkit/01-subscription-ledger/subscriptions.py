"""Subscription and license cost logic for a SaaS portfolio.

Pure functions only. Each takes plain values and returns plain values, with no
file or console access. The CLI layer in cli.py does the reading and writing, and
the browser app in 02 mirrors this same math to the cent.

For each subscription it works out the monthly and annual cost, how many paid
seats sit unused and what that waste is worth, how close the renewal is, and a
plain action for the owner: confirm an upcoming auto-renewal, reduce seats on an
underused plan, or review an expired one.

All money is decimal.Decimal rounded half up to the cent.
"""

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
RATIO = Decimal("0.0001")

# A per-seat plan used below this share of its seats is called underused.
UNDERUSED_BELOW = Decimal("0.70")
# A renewal this many days out or fewer is treated as due soon.
DUE_SOON_DAYS = 30
UPCOMING_DAYS = 90


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def ratio(value):
    return value.quantize(RATIO, rounding=ROUND_HALF_UP)


def monthly_cost(plan_type, monthly_unit_cost, seats_owned):
    """Cost per month. Per-seat plans pay for every owned seat; flat plans pay one
    fixed amount regardless of seats."""
    if plan_type == "per_seat":
        return money(monthly_unit_cost * Decimal(seats_owned))
    return money(monthly_unit_cost)


def unused_seats(plan_type, seats_owned, seats_used):
    """Paid seats that nobody is using. Flat plans have no seat waste."""
    if plan_type == "per_seat":
        return seats_owned - seats_used
    return 0


def monthly_waste(plan_type, monthly_unit_cost, seats_owned, seats_used):
    """Monthly spend on unused seats."""
    if plan_type == "per_seat":
        return money(monthly_unit_cost * Decimal(unused_seats(plan_type, seats_owned, seats_used)))
    return Decimal("0.00")


def utilization(plan_type, seats_owned, seats_used):
    """Share of owned seats in use, as a ratio. None for a flat plan."""
    if plan_type != "per_seat":
        return None
    if seats_owned <= 0:
        return Decimal("0.0000")
    return ratio(Decimal(seats_used) / Decimal(seats_owned))


def renewal_status(days_to_renewal):
    """Label a renewal from how many days out it is."""
    if days_to_renewal < 0:
        return "Expired"
    if days_to_renewal <= DUE_SOON_DAYS:
        return "Due soon"
    if days_to_renewal <= UPCOMING_DAYS:
        return "Upcoming"
    return "Current"


def action(plan_type, days_to_renewal, auto_renew, util):
    """A plain next step for the subscription owner."""
    if days_to_renewal < 0:
        return "Expired, review"
    renews_soon = auto_renew and days_to_renewal <= DUE_SOON_DAYS
    underused = util is not None and util < UNDERUSED_BELOW
    if renews_soon and underused:
        return "Auto-renews soon, underused"
    if renews_soon:
        return "Auto-renews soon"
    if underused:
        return "Underused"
    return "OK"


def subscription_row(sub, as_of):
    """Build the full result row for one validated subscription.

    sub holds a Decimal monthly_unit_cost, integer seats, a date renewal_date, a
    bool auto_renew, and the string fields. as_of is the date the renewal clock is
    measured from.
    """
    mc = monthly_cost(sub["plan_type"], sub["monthly_unit_cost"], sub["seats_owned"])
    mw = monthly_waste(sub["plan_type"], sub["monthly_unit_cost"], sub["seats_owned"], sub["seats_used"])
    util = utilization(sub["plan_type"], sub["seats_owned"], sub["seats_used"])
    days = (sub["renewal_date"] - as_of).days
    return {
        "sub_id": sub["sub_id"],
        "vendor": sub["vendor"],
        "plan": sub["plan"],
        "plan_type": sub["plan_type"],
        "monthly_unit_cost": money(sub["monthly_unit_cost"]),
        "seats_owned": sub["seats_owned"],
        "seats_used": sub["seats_used"],
        "monthly_cost": mc,
        "annual_cost": money(mc * 12),
        "unused_seats": unused_seats(sub["plan_type"], sub["seats_owned"], sub["seats_used"]),
        "monthly_waste": mw,
        "annual_waste": money(mw * 12),
        "utilization": util,
        "renewal_date": sub["renewal_date"].isoformat(),
        "days_to_renewal": days,
        "renewal_status": renewal_status(days),
        "auto_renew": "yes" if sub["auto_renew"] else "no",
        "action": action(sub["plan_type"], days, sub["auto_renew"], util),
    }


def summarize(subs, as_of):
    """Build the per-subscription rows and the portfolio totals."""
    rows = [subscription_row(sub, as_of) for sub in subs]

    def total(field):
        return money(sum((r[field] for r in rows), Decimal("0.00")))

    totals = {
        "monthly_cost": total("monthly_cost"),
        "annual_cost": total("annual_cost"),
        "monthly_waste": total("monthly_waste"),
        "annual_waste": total("annual_waste"),
        "due_soon_count": sum(1 for r in rows if r["renewal_status"] == "Due soon"),
        "expired_count": sum(1 for r in rows if r["renewal_status"] == "Expired"),
        "underused_count": sum(
            1 for r in rows if r["utilization"] is not None and r["utilization"] < UNDERUSED_BELOW
        ),
    }
    return {"per_sub": rows, "totals": totals}
