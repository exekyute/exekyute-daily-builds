"""Pure excise-duty logic for packaged beer.

No file or console I/O lives here. The rates are the Canada Revenue Agency rates
of excise duty on beer brewed in Canada, per hectolitre, effective April 1, 2026.
The reduced-rate brackets apply to the first 75,000 hL of annual production; the
regular rate applies above that. Update these figures when the CRA publishes the
next April 1 adjustment.

Volume is converted to hectolitres at 100 litres each. Duty is carried as
decimal.Decimal and quantized half up to the cent.
"""

from decimal import Decimal, ROUND_HALF_UP

CENTS = Decimal("0.01")

ABV_CLASSES = ("over_2_5", "over_1_2_to_2_5", "not_over_1_2")

# Regular rate per hL, for annual production above the 75,000 hL limit.
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


def money(value):
    """Quantize a value to cents, rounding half up."""
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


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


def run_excise(events, ytd_hectolitres):
    """Thread packaging events through the brackets and total duty by ABV class.

    `events` is a list of dicts with `abv_class` and `litres`, processed in order.
    A single cumulative production figure starts at `ytd_hectolitres` and runs
    through every event, so the order of packaging sets the bracket each volume
    falls in. Returns a list of per-class summary dicts and the cumulative figure
    reached.
    """
    cumulative = Decimal(ytd_hectolitres)
    by_class = {}
    for event in events:
        abv_class = event["abv_class"]
        hl = litres_to_hectolitres(event["litres"])
        duty, cumulative = excise_for_volume(hl, abv_class, cumulative)
        hl_sum, duty_sum = by_class.get(abv_class, (Decimal("0"), Decimal("0")))
        by_class[abv_class] = (hl_sum + hl, duty_sum + duty)

    summary = []
    for abv_class in ABV_CLASSES:
        if abv_class in by_class:
            hl_sum, duty_sum = by_class[abv_class]
            summary.append({
                "abv_class": abv_class,
                "hectolitres": hl_sum.quantize(CENTS, rounding=ROUND_HALF_UP),
                "excise_duty": money(duty_sum),
            })
    return summary, cumulative


def total_duty(summary):
    """Total excise duty across the per-class summary."""
    return money(sum(row["excise_duty"] for row in summary))
