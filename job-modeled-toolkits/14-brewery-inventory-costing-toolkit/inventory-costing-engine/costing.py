"""Pure costing logic for the brewery inventory engine.

No file or console I/O lives here. Every function takes values and returns
values, which is what lets the unit tests check the numbers directly. Money is
carried as decimal.Decimal and quantized half up, never as float, so the
results agree to the cent with the SQL reconciliation tool downstream.
"""

from decimal import Decimal, ROUND_HALF_UP

CENTS = Decimal("0.01")
WAC_PLACES = Decimal("0.0001")  # weighted-average unit cost shown to 4 places

# Volume units convert to litres by a fixed factor. Discrete units such as a
# case, keg, or single can are not a fixed volume, so they convert through a
# litres-per-unit figure the caller supplies from the product master.
LITRES_PER_UNIT = {
    "ml": Decimal("0.001"),
    "l": Decimal("1"),
    "hl": Decimal("100"),
    "bbl": Decimal("117.347765"),  # US beer barrel
}

ABV_CLASSES = ("over_2_5", "over_1_2_to_2_5", "not_over_1_2")

# Rates of excise duty on beer brewed in Canada, per hectolitre, effective
# April 1, 2026 (CRA). The regular rate applies to annual production above the
# 75,000 hL limit; the reduced brackets apply to the first 75,000 hL. Update
# these figures when CRA publishes the next April 1 adjustment.
REGULAR_RATE = {
    "over_2_5": Decimal("37.69"),
    "over_1_2_to_2_5": Decimal("18.85"),
    "not_over_1_2": Decimal("3.128"),
}

# (upper bound in hL, rate per hL) for each reduced bracket, in order. The last
# bound is the 75,000 hL production limit; volume past it uses REGULAR_RATE.
REDUCED_BRACKETS = {
    "over_2_5": [
        (Decimal("2000"), Decimal("3.769")),
        (Decimal("5000"), Decimal("7.538")),
        (Decimal("15000"), Decimal("15.076")),
        (Decimal("50000"), Decimal("26.383")),
        (Decimal("75000"), Decimal("32.037")),
    ],
    "over_1_2_to_2_5": [
        (Decimal("2000"), Decimal("1.885")),
        (Decimal("5000"), Decimal("3.770")),
        (Decimal("15000"), Decimal("7.540")),
        (Decimal("50000"), Decimal("13.195")),
        (Decimal("75000"), Decimal("16.023")),
    ],
    "not_over_1_2": [
        (Decimal("2000"), Decimal("0.3128")),
        (Decimal("5000"), Decimal("0.6256")),
        (Decimal("15000"), Decimal("1.2512")),
        (Decimal("50000"), Decimal("2.1896")),
        (Decimal("75000"), Decimal("2.6588")),
    ],
}

RECEIPT_TYPES = ("opening", "receipt", "package")


def money(value):
    """Quantize a value to cents, rounding half up."""
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def landed_value(quantity, unit_price, freight, customs_duty):
    """Total landed cost of a receipt: purchase price plus freight plus duty."""
    purchase = Decimal(quantity) * Decimal(unit_price)
    return money(purchase + Decimal(freight) + Decimal(customs_duty))


def update_weighted_average(on_hand_qty, on_hand_value, receipt_qty, receipt_value):
    """Fold a receipt into the running balance and return (qty, value)."""
    new_qty = Decimal(on_hand_qty) + Decimal(receipt_qty)
    new_value = money(Decimal(on_hand_value) + Decimal(receipt_value))
    return new_qty, new_value


def issue_cost(on_hand_qty, on_hand_value, issue_qty):
    """Cost of an issue, valued at the current weighted-average unit cost."""
    on_hand_qty = Decimal(on_hand_qty)
    if on_hand_qty == 0:
        unit = Decimal("0")
    else:
        unit = Decimal(on_hand_value) / on_hand_qty
    return money(unit * Decimal(issue_qty))


def weighted_average_unit_cost(on_hand_qty, on_hand_value):
    """Current weighted-average unit cost, shown to four decimal places."""
    on_hand_qty = Decimal(on_hand_qty)
    if on_hand_qty == 0:
        return Decimal("0").quantize(WAC_PLACES)
    return (Decimal(on_hand_value) / on_hand_qty).quantize(
        WAC_PLACES, rounding=ROUND_HALF_UP
    )


def to_litres(quantity, unit, litres_per_unit=None):
    """Convert a quantity to litres. Volume units use a fixed factor; discrete
    units (case, keg, can) need a litres-per-unit figure from the product master."""
    key = unit.strip().lower()
    if key in LITRES_PER_UNIT:
        return Decimal(quantity) * LITRES_PER_UNIT[key]
    if litres_per_unit is None:
        raise ValueError(
            "unit '%s' needs a litres-per-unit figure to convert to litres" % unit
        )
    return Decimal(quantity) * Decimal(litres_per_unit)


def litres_to_hectolitres(litres):
    """100 litres to the hectolitre."""
    return Decimal(litres) / Decimal("100")


def excise_for_volume(hectolitres, abv_class, cumulative_before):
    """Excise duty on one packaging event.

    `hectolitres` is the volume of one ABV class being packaged. `cumulative_before`
    is the total beer of every class already brewed this calendar year, which sets
    where this volume falls in the reduced-rate brackets. The volume is split across
    every bracket it spans, then anything past 75,000 hL is charged the regular rate.
    Returns (duty, cumulative_after); the duty is unrounded so the caller can total
    by class and quantize once.
    """
    if abv_class not in REDUCED_BRACKETS:
        raise ValueError("unknown ABV class '%s'" % abv_class)
    remaining = Decimal(hectolitres)
    position = Decimal(cumulative_before)
    duty = Decimal("0")
    for upper, rate in REDUCED_BRACKETS[abv_class]:
        if remaining <= 0:
            break
        if position >= upper:
            continue
        take = min(remaining, upper - position)
        duty += take * rate
        position += take
        remaining -= take
    if remaining > 0:  # past the 75,000 hL limit, regular rate applies
        duty += remaining * REGULAR_RATE[abv_class]
        position += remaining
    return duty, position


def run_ledger(transactions):
    """Replay one SKU's transactions in order and return its ending position.

    Each transaction is a dict with Decimal values for quantity, unit_price,
    freight, and customs_duty, plus a txn_type. Receipts (opening, receipt,
    package) raise the weighted-average balance; issues draw it down at the
    current weighted-average cost. On-hand going below zero sets an integrity
    flag rather than stopping the run, so bad data surfaces instead of hiding.
    """
    qty = Decimal("0")
    value = Decimal("0")
    flag = ""
    for txn in transactions:
        txn_type = txn["txn_type"]
        if txn_type in RECEIPT_TYPES:
            received = landed_value(
                txn["quantity"], txn["unit_price"], txn["freight"], txn["customs_duty"]
            )
            qty, value = update_weighted_average(qty, value, txn["quantity"], received)
        elif txn_type == "issue":
            cost = issue_cost(qty, value, txn["quantity"])
            qty = qty - Decimal(txn["quantity"])
            value = money(value - cost)
        if qty < 0:
            flag = "negative on-hand"
    return {
        "on_hand_qty": qty,
        "on_hand_value": value,
        "wac_unit_cost": weighted_average_unit_cost(qty, value),
        "integrity_flag": flag,
    }
