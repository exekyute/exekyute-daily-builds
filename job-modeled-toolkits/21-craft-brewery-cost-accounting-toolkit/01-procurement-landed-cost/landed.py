"""Pure landed-cost logic for the procurement engine.

No file or console I/O lives here. Every function takes values and returns
values, which is what lets the unit tests check the numbers directly. Money is
carried as decimal.Decimal and quantized half up, never as float, so the landed
unit costs agree to the cent with the batch costing and valuation tools
downstream.

A purchase order can carry several lines under one freight bill. Freight is
spread across the lines of a purchase order by each line's extended value, using
the largest-remainder method so the allocated cents sum back to the freight
total exactly, with nothing gained or lost. Import duty is charged per line as a
percentage of that line's extended value, which models the CRA customs duty on
goods such as imported hops.
"""

from decimal import Decimal, ROUND_HALF_UP

CENTS = Decimal("0.01")
UNIT_COST_PLACES = Decimal("0.0001")  # landed unit cost shown to 4 places

CATEGORIES = ("raw_material", "packaging_material")


def money(value):
    """Quantize a value to cents, rounding half up."""
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def extended_value(quantity, unit_price):
    """Purchase value of a line before freight and duty: quantity times price."""
    return money(Decimal(quantity) * Decimal(unit_price))


def allocate_freight(extended_values, freight_total):
    """Split a freight total across lines by extended value, to the cent.

    Returns a list of Decimal allocations the same length as `extended_values`,
    summing exactly to `freight_total`. Each line gets the floor of its
    proportional share in cents; the leftover cents are handed out one at a time
    to the lines with the largest fractional remainder. When every line has a
    zero extended value the freight is spread as evenly as cents allow.
    """
    freight = money(freight_total)
    count = len(extended_values)
    if count == 0:
        return []
    total = sum(Decimal(v) for v in extended_values)

    cents_total = int((freight / CENTS).to_integral_value(rounding=ROUND_HALF_UP))
    shares = []
    if total > 0:
        for value in extended_values:
            exact = (Decimal(value) / total) * Decimal(cents_total)
            floor = int(exact.to_integral_value(rounding="ROUND_FLOOR"))
            shares.append([floor, exact - Decimal(floor)])
    else:
        base = cents_total // count
        for index in range(count):
            shares.append([base, Decimal(index)])  # tie-break by position

    handed_out = sum(share[0] for share in shares)
    leftover = cents_total - handed_out
    order = sorted(range(count), key=lambda i: shares[i][1], reverse=True)
    for index in order[:leftover]:
        shares[index][0] += 1

    return [Decimal(share[0]) * CENTS for share in shares]


def duty_amount(extended, duty_rate):
    """Import duty on a line: extended value times the duty rate percentage."""
    return money(Decimal(extended) * (Decimal(duty_rate) / Decimal("100")))


def landed_unit_cost(landed_total, quantity):
    """Landed cost per unit, shown to four decimal places."""
    quantity = Decimal(quantity)
    if quantity == 0:
        return Decimal("0").quantize(UNIT_COST_PLACES)
    return (Decimal(landed_total) / quantity).quantize(
        UNIT_COST_PLACES, rounding=ROUND_HALF_UP
    )


def cost_purchase_order(lines):
    """Cost one purchase order's lines and return a list of landed-cost dicts.

    Each input line is a dict with Decimal quantity, unit_price, freight_total,
    and duty_rate. The freight_total is the same figure on every line of the
    order; it is allocated once across the lines by extended value. Duty is per
    line. The returned dicts carry the extended value, the freight allocated to
    the line, the duty, the landed total, and the landed unit cost.
    """
    extended = [extended_value(line["quantity"], line["unit_price"]) for line in lines]
    freight_total = lines[0]["freight_total"] if lines else Decimal("0")
    freight_alloc = allocate_freight(extended, freight_total)

    results = []
    for line, ext, freight in zip(lines, extended, freight_alloc):
        duty = duty_amount(ext, line["duty_rate"])
        landed_total = money(ext + freight + duty)
        results.append(
            {
                "po_id": line["po_id"],
                "line_id": line["line_id"],
                "sku": line["sku"],
                "description": line["description"],
                "category": line["category"],
                "quantity": Decimal(line["quantity"]),
                "unit": line["unit"],
                "unit_price": Decimal(line["unit_price"]),
                "extended_value": ext,
                "freight_alloc": freight,
                "duty": duty,
                "landed_total": landed_total,
                "landed_unit_cost": landed_unit_cost(landed_total, line["quantity"]),
            }
        )
    return results


def cost_all(lines):
    """Cost every purchase order in a file, grouped by po_id in first-seen order."""
    order = []
    groups = {}
    for line in lines:
        po_id = line["po_id"]
        if po_id not in groups:
            groups[po_id] = []
            order.append(po_id)
        groups[po_id].append(line)

    results = []
    for po_id in order:
        results.extend(cost_purchase_order(groups[po_id]))
    return results
