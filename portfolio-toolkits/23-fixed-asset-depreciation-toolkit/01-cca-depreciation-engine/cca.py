"""Depreciation logic for the fixed-asset engine.

Pure functions only: each takes plain values and returns plain values, with no
file or console access. The CLI layer in cli.py handles all reading and writing.

Two parallel sets of numbers are produced for every asset and class:

  Book depreciation  - straight-line per asset, what the financial statements carry.
  Capital Cost Allowance (CCA) - the Canada Revenue Agency declining-balance
                       deduction, calculated per class pool, what the tax return uses.

All money is handled with decimal.Decimal and rounded half up to the cent, so the
figures match the SQL runner and the browser dashboard exactly.
"""

from decimal import Decimal, ROUND_HALF_UP

# CRA Capital Cost Allowance rates by class, 2026 tax year.
# Declining-balance rates from the CRA CCA class list. Stored here so the rule
# lives with the code that applies it. Review against the CRA class list each year.
CCA_RATES = {
    "1": Decimal("0.04"),     # Most buildings acquired after 1987
    "8": Decimal("0.20"),     # Furniture, fixtures, equipment not in another class
    "10": Decimal("0.30"),    # General-purpose vehicles and equipment
    "12": Decimal("1.00"),    # Tools, small assets written off in full
    "50": Decimal("0.55"),    # Computer hardware and systems software
    "53": Decimal("0.50"),    # Manufacturing and processing machinery
    "14.1": Decimal("0.05"),  # Goodwill and other intangibles
}

CENT = Decimal("0.01")


def money(value):
    """Round a Decimal to the cent, half up. Keeps every figure fixed-point."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def book_depreciation(capital_cost, salvage_value, useful_life_years, prior_accum):
    """Straight-line book depreciation for one asset for the current year.

    Returns the annual charge, the current-year charge, the accumulated total,
    and the net book value. The current-year charge is capped so accumulated
    depreciation never passes the depreciable base (cost less salvage), which is
    what makes a fully depreciated asset take zero in later years.
    """
    depreciable_base = capital_cost - salvage_value
    if useful_life_years <= 0:
        raise ValueError("useful_life_years must be greater than zero")

    annual = money(depreciable_base / Decimal(useful_life_years))
    remaining = depreciable_base - prior_accum
    if remaining <= Decimal("0"):
        current = Decimal("0.00")
    else:
        current = annual if annual <= remaining else money(remaining)

    accum = money(prior_accum + current)
    net_book_value = money(capital_cost - accum)
    return {
        "annual_book_dep": money(annual),
        "current_book_dep": money(current),
        "accum_book_dep": accum,
        "net_book_value": net_book_value,
    }


def class_cca(cca_class, opening_ucc, additions, disposals, assets_remaining):
    """Capital Cost Allowance rollforward for one class pool for the year.

    Steps, in order:
      1. Undepreciated capital cost before CCA = opening + additions - disposals.
      2. If that is negative, the excess is recapture (added back to income),
         the pool resets to zero, and no CCA is taken.
      3. If the pool is positive but no assets remain in the class, the remainder
         is a terminal loss, the pool goes to zero, and no CCA is taken.
      4. Otherwise apply the half-year rule (half of net additions is held back
         from the base in the acquisition year), then CCA = rate x base, and
         closing UCC = pool before CCA - CCA.
    """
    rate = CCA_RATES[cca_class]
    ucc_before_cca = opening_ucc + additions - disposals

    recapture = Decimal("0.00")
    terminal_loss = Decimal("0.00")
    half_year_adjustment = Decimal("0.00")
    cca_base = Decimal("0.00")
    cca = Decimal("0.00")

    if ucc_before_cca < Decimal("0"):
        recapture = money(-ucc_before_cca)
        closing_ucc = Decimal("0.00")
    elif assets_remaining == 0 and ucc_before_cca > Decimal("0"):
        terminal_loss = money(ucc_before_cca)
        closing_ucc = Decimal("0.00")
    else:
        net_additions = additions - disposals
        if net_additions > Decimal("0"):
            half_year_adjustment = money(net_additions / Decimal("2"))
        cca_base = money(ucc_before_cca - half_year_adjustment)
        cca = money(rate * cca_base)
        closing_ucc = money(ucc_before_cca - cca)

    return {
        "cca_class": cca_class,
        "rate": rate,
        "opening_ucc": money(opening_ucc),
        "additions": money(additions),
        "disposals": money(disposals),
        "half_year_adjustment": half_year_adjustment,
        "cca_base": cca_base,
        "cca": cca,
        "recapture": recapture,
        "terminal_loss": terminal_loss,
        "closing_ucc": closing_ucc,
    }


def compute_schedules(assets, opening_ucc, tax_year):
    """Build the per-asset book schedule and the per-class CCA rollforward.

    assets is a list of dicts with Decimal money fields and an integer
    in_service_year, already parsed and validated. opening_ucc maps a class to
    its undepreciated capital cost carried in from the prior year. tax_year is
    the year whose acquisitions are treated as current-year additions and so are
    subject to the half-year rule.
    """
    per_asset = []
    for asset in assets:
        book = book_depreciation(
            asset["capital_cost"],
            asset["salvage_value"],
            asset["useful_life_years"],
            asset["prior_accum_book_dep"],
        )
        # A disposed asset leaves the books, so it takes no current-year charge
        # and its accumulated balance stays at the prior-year figure.
        if asset["disposed"]:
            book["current_book_dep"] = Decimal("0.00")
            book["accum_book_dep"] = money(asset["prior_accum_book_dep"])
            book["net_book_value"] = Decimal("0.00")
        per_asset.append({
            "asset_id": asset["asset_id"],
            "description": asset["description"],
            "cca_class": asset["cca_class"],
            "capital_cost": money(asset["capital_cost"]),
            "salvage_value": money(asset["salvage_value"]),
            "useful_life_years": asset["useful_life_years"],
            "in_service_date": asset["in_service_date"],
            "disposed": asset["disposed"],
            "annual_book_dep": book["annual_book_dep"],
            "prior_accum_book_dep": money(asset["prior_accum_book_dep"]),
            "current_book_dep": book["current_book_dep"],
            "accum_book_dep": book["accum_book_dep"],
            "net_book_value": book["net_book_value"],
        })

    classes = sorted(set(list(opening_ucc.keys()) + [a["cca_class"] for a in assets]))
    per_class = []
    for cca_class in classes:
        class_assets = [a for a in assets if a["cca_class"] == cca_class]
        additions = sum(
            (a["capital_cost"] for a in class_assets if a["in_service_year"] == tax_year),
            Decimal("0.00"),
        )
        disposals = sum(
            (min(a["disposal_proceeds"], a["capital_cost"]) for a in class_assets if a["disposed"]),
            Decimal("0.00"),
        )
        assets_remaining = sum(1 for a in class_assets if not a["disposed"])
        opening = opening_ucc.get(cca_class, Decimal("0.00"))

        row = class_cca(cca_class, opening, additions, disposals, assets_remaining)

        # Net book value of the assets the class still carries, and the resulting
        # book-versus-tax temporary difference against the closing UCC.
        nbv = sum(
            (pa["net_book_value"] for pa in per_asset
             if pa["cca_class"] == cca_class and not pa["disposed"]),
            Decimal("0.00"),
        )
        row["net_book_value"] = money(nbv)
        row["temporary_difference"] = money(nbv - row["closing_ucc"])
        per_class.append(row)

    return per_asset, per_class
