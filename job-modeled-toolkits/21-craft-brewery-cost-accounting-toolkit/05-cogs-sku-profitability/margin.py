"""Pure cost-of-goods-sold and margin logic.

No file or console I/O lives here. Money is carried as decimal.Decimal and
quantized half up to the cent, never as float.

A finished good's cost of goods sold has two parts: the production cost from the
batch tool (materials, labour, overhead, and packaging, divided over the units
made) and the federal excise duty attributable to the volume sold. The excise
rate per litre comes from the excise tool's duty for the ABV class divided by the
litres that class packaged. Gross margin is revenue minus that cost of goods sold.
"""

from decimal import Decimal, ROUND_HALF_UP

CENTS = Decimal("0.01")
PCT = Decimal("0.01")

CHANNELS = ("retail", "on_premise", "distributor")


def money(value):
    """Quantize a value to cents, rounding half up."""
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def class_packaged_litres(finished_rows):
    """Total packaged litres by ABV class, from the batch tool's finished units."""
    totals = {}
    for row in finished_rows:
        abv = row["abv_class"]
        totals[abv] = totals.get(abv, Decimal("0")) + Decimal(row["packaged_litres"])
    return totals


def excise_rate_per_litre(excise_rows, class_litres):
    """Excise duty per litre by ABV class: class duty divided by class litres.

    Kept at full precision so the per-unit excise quantizes once.
    """
    rates = {}
    for row in excise_rows:
        abv = row["abv_class"]
        litres = class_litres.get(abv, Decimal("0"))
        rates[abv] = Decimal(row["excise_duty"]) / litres if litres else Decimal("0")
    return rates


def sku_cost_basis(finished_rows, excise_rates):
    """Per-SKU production unit cost, excise per unit, and reference data.

    Production unit cost is the batch line cost divided by units made, at full
    precision. Excise per unit is the class rate per litre times the litres in
    one unit. Returns {fg_sku: {...}}.
    """
    basis = {}
    for row in finished_rows:
        units = Decimal(row["units"])
        litres = Decimal(row["packaged_litres"])
        litres_per_unit = litres / units if units else Decimal("0")
        production_unit = Decimal(row["line_cost"]) / units if units else Decimal("0")
        excise_per_unit = excise_rates.get(row["abv_class"], Decimal("0")) * litres_per_unit
        basis[row["fg_sku"]] = {
            "product_line": row["product_line"],
            "abv_class": row["abv_class"],
            "units_made": units,
            "production_unit_cost": production_unit,
            "excise_per_unit": excise_per_unit,
        }
    return basis


def margin_line(sale, basis):
    """Cost out one sales line and return a margin dict.

    `sale` carries fg_sku, channel, units_sold, and unit_price. `basis` is the
    per-SKU dict from sku_cost_basis.
    """
    info = basis[sale["fg_sku"]]
    units = Decimal(sale["units_sold"])
    revenue = money(Decimal(sale["unit_price"]) * units)
    cogs_production = money(info["production_unit_cost"] * units)
    cogs_excise = money(info["excise_per_unit"] * units)
    cogs_total = money(cogs_production + cogs_excise)
    gross_margin = money(revenue - cogs_total)
    margin_pct = (gross_margin / revenue * Decimal("100")).quantize(PCT, rounding=ROUND_HALF_UP) if revenue else Decimal("0.00")
    return {
        "fg_sku": sale["fg_sku"],
        "product_line": info["product_line"],
        "channel": sale["channel"],
        "units_sold": units,
        "unit_price": money(sale["unit_price"]),
        "revenue": revenue,
        "cogs_production": cogs_production,
        "cogs_excise": cogs_excise,
        "cogs_total": cogs_total,
        "gross_margin": gross_margin,
        "margin_pct": margin_pct,
    }


def cost_sales(sales, basis):
    """Cost every sales line. Returns a list of margin dicts in file order."""
    return [margin_line(sale, basis) for sale in sales]


def _aggregate(lines, key):
    groups = {}
    order = []
    for line in lines:
        k = line[key]
        if k not in groups:
            groups[k] = {"revenue": Decimal("0"), "cogs_total": Decimal("0"),
                         "gross_margin": Decimal("0"), "units_sold": Decimal("0")}
            order.append(k)
        groups[k]["revenue"] += line["revenue"]
        groups[k]["cogs_total"] += line["cogs_total"]
        groups[k]["gross_margin"] += line["gross_margin"]
        groups[k]["units_sold"] += line["units_sold"]
    out = []
    for k in order:
        g = groups[k]
        margin_pct = (g["gross_margin"] / g["revenue"] * Decimal("100")).quantize(PCT, rounding=ROUND_HALF_UP) if g["revenue"] else Decimal("0.00")
        out.append({key: k, "units_sold": g["units_sold"], "revenue": money(g["revenue"]),
                    "cogs_total": money(g["cogs_total"]), "gross_margin": money(g["gross_margin"]),
                    "margin_pct": margin_pct})
    return out


def by_product_line(lines):
    return _aggregate(lines, "product_line")


def by_channel(lines):
    return _aggregate(lines, "channel")


def totals(lines):
    revenue = money(sum(l["revenue"] for l in lines))
    cogs = money(sum(l["cogs_total"] for l in lines))
    margin = money(revenue - cogs)
    return {"revenue": revenue, "cogs_total": cogs, "gross_margin": margin}
