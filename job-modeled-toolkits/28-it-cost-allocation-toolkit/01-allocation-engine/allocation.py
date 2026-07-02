"""Cost-allocation logic for an IT showback.

Pure functions only. Each takes plain values and returns plain values, with no
file or console access. The CLI layer in cli.py reads and writes; the workbook
builder in 02 turns the result into a chargeback workbook.

The job is to split a pool of shared IT costs across departments by a driver such
as headcount, so each department sees its share of every cost item. Each item is
split with the largest-remainder method, so the parts sum to the item exactly with
no cent lost, and the department totals therefore sum to the whole pool.

All money is decimal.Decimal rounded half up to the cent.
"""

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
RATIO = Decimal("0.0001")


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def ratio(value):
    return value.quantize(RATIO, rounding=ROUND_HALF_UP)


def allocate_amount(amount, weights):
    """Split amount across the keys of weights in proportion to each weight.

    Works in whole cents so the parts sum to amount exactly. Each share is floored
    to the cent, then the leftover cents go one at a time to the keys with the
    largest fractional remainder, ties broken by key name so the result is
    deterministic. With every weight zero the amount is split as evenly as the
    cents allow.
    """
    names = sorted(weights)
    total_cents = int((money(amount) / CENT).to_integral_value(rounding=ROUND_HALF_UP))
    if not names or total_cents == 0:
        return {name: Decimal("0.00") for name in names}

    total_weight = sum(weights.values())
    if total_weight <= 0:
        effective = {name: Decimal("1") for name in names}
        total_weight = Decimal(len(names))
    else:
        effective = weights

    raw = {name: Decimal(total_cents) * Decimal(effective[name]) / Decimal(total_weight) for name in names}
    floor_cents = {name: int(raw[name] // 1) for name in names}
    remainder = total_cents - sum(floor_cents.values())
    fractional = {name: raw[name] - floor_cents[name] for name in names}
    order = sorted(names, key=lambda name: (-fractional[name], name))
    for i in range(remainder):
        floor_cents[order[i]] += 1
    return {name: money(Decimal(floor_cents[name]) / Decimal("100")) for name in names}


def build_allocation(pool_items, drivers):
    """Allocate every pool item across the departments by their driver weight.

    pool_items is a list of (item, Decimal amount) in order. drivers is a dict of
    department to Decimal driver value. Returns the per-department rows (driver,
    a per-item allocation map, and the department total) and the column totals.
    """
    departments = sorted(drivers)
    total_driver = sum(drivers.values())
    pool_total = money(sum((amount for _item, amount in pool_items), Decimal("0.00")))

    per_item = {}
    for item, amount in pool_items:
        per_item[item] = allocate_amount(amount, drivers)

    rows = []
    for dept in departments:
        allocations = {item: per_item[item][dept] for item, _ in pool_items}
        dept_total = money(sum(allocations.values(), Decimal("0.00")))
        rows.append({
            "department": dept,
            "driver_value": drivers[dept],
            "allocations": allocations,
            "total": dept_total,
            "pct_of_pool": ratio(dept_total / pool_total) if pool_total > 0 else Decimal("0.0000"),
        })

    column_totals = {item: money(sum((per_item[item][d] for d in departments), Decimal("0.00")))
                     for item, _ in pool_items}
    return {
        "departments": departments,
        "items": [item for item, _ in pool_items],
        "item_amounts": {item: money(amount) for item, amount in pool_items},
        "total_driver": total_driver,
        "pool_total": pool_total,
        "rows": rows,
        "column_totals": column_totals,
        "allocated_total": money(sum((r["total"] for r in rows), Decimal("0.00"))),
    }
