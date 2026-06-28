"""Pure batch-costing logic for the brewery.

No file or console I/O lives here. Money is carried as decimal.Decimal and
quantized half up to the cent, never as float, so the batch costs agree with the
valuation and margin tools downstream.

A batch starts as wort (brewed litres) and finishes as packaged beer (finished
litres); the difference is yield loss, which is absorbed into the cost of the
good beer that survives. The cost of a batch is the cost of its ingredients
valued at the period weighted-average landed cost, plus direct labour and
overhead. That brew cost is spread across the batch's packaging runs by packaged
volume, then each run picks up the cost of its own cans, labels, or kegs.
"""

from decimal import Decimal, ROUND_HALF_UP

CENTS = Decimal("0.01")
UNIT_COST_PLACES = Decimal("0.0001")
RATE_PLACES = Decimal("0.000001")  # cost per litre, carried fine for allocation


def money(value):
    """Quantize a value to cents, rounding half up."""
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def weighted_average_costs(landed_rows):
    """Period weighted-average landed cost per SKU: total landed value / total qty.

    Kept at full precision so the cost lines below quantize once, the same way
    the perpetual valuation tool values issues. Returns {sku: Decimal}.
    """
    totals = {}
    for row in landed_rows:
        sku = row["sku"]
        value, qty = totals.get(sku, (Decimal("0"), Decimal("0")))
        totals[sku] = (
            value + Decimal(row["landed_total"]),
            qty + Decimal(row["quantity"]),
        )
    costs = {}
    for sku, (value, qty) in totals.items():
        costs[sku] = value / qty if qty else Decimal("0")
    return costs


def allocate_by_weights(amount, weights):
    """Split a cent amount across lines by weight, largest remainder to the cent.

    Returns a list of Decimal allocations summing exactly to `amount`.
    """
    amount = money(amount)
    count = len(weights)
    if count == 0:
        return []
    total = sum(Decimal(w) for w in weights)
    cents_total = int((amount / CENTS).to_integral_value(rounding=ROUND_HALF_UP))

    shares = []
    if total > 0:
        for weight in weights:
            exact = (Decimal(weight) / total) * Decimal(cents_total)
            floor = int(exact.to_integral_value(rounding="ROUND_FLOOR"))
            shares.append([floor, exact - Decimal(floor)])
    else:
        base = cents_total // count
        for index in range(count):
            shares.append([base, Decimal(index)])

    leftover = cents_total - sum(s[0] for s in shares)
    order = sorted(range(count), key=lambda i: shares[i][1], reverse=True)
    for index in order[:leftover]:
        shares[index][0] += 1
    return [Decimal(s[0]) * CENTS for s in shares]


def ingredient_cost(ingredients, wac):
    """Cost of a batch's ingredient lines at weighted-average landed cost.

    `ingredients` is a list of dicts with sku and quantity. Each line is valued
    at the SKU's weighted-average cost and quantized to the cent, then summed.
    Returns (total, lines) where lines carry the per-line cost.
    """
    lines = []
    total = Decimal("0")
    for item in ingredients:
        sku = item["sku"]
        cost = money(Decimal(item["quantity"]) * wac[sku])
        total += cost
        lines.append({"sku": sku, "quantity": Decimal(item["quantity"]), "cost": cost})
    return total, lines


def package_unit_material_cost(container_sku, label_sku, wac):
    """Material cost of one packaged unit: its container plus its label, if any."""
    cost = wac[container_sku]
    if label_sku:
        cost += wac[label_sku]
    return cost


def cost_per_litre(brew_cost, finished_litres):
    """Brew cost spread over the good beer that survives to packaging."""
    finished = Decimal(finished_litres)
    if finished == 0:
        return Decimal("0").quantize(RATE_PLACES)
    return (Decimal(brew_cost) / finished).quantize(RATE_PLACES, rounding=ROUND_HALF_UP)


def cost_batch(batch, ingredients, runs, wac):
    """Cost one batch and its packaging runs.

    Returns a dict with the batch summary and a list of finished-unit rows, one
    per packaging run. The brew cost (ingredients plus labour plus overhead) is
    allocated across the runs by packaged litres; each run then adds the cost of
    its own packaging materials. The finished-unit costs sum back to the total
    batch cost exactly.
    """
    ing_total, _ = ingredient_cost(ingredients, wac)
    labour = money(batch["labour_cost"])
    overhead = money(batch["overhead_cost"])
    brew_cost = money(ing_total + labour + overhead)

    packaged_litres = [Decimal(r["units"]) * Decimal(r["litres_per_unit"]) for r in runs]
    beer_alloc = allocate_by_weights(brew_cost, packaged_litres)

    finished_rows = []
    packaging_material_total = Decimal("0")
    for run, litres, beer in zip(runs, packaged_litres, beer_alloc):
        units = Decimal(run["units"])
        per_unit_material = package_unit_material_cost(
            run["container_sku"], run.get("label_sku") or "", wac
        )
        material_cost = money(units * per_unit_material)
        packaging_material_total += material_cost
        line_cost = money(beer + material_cost)
        unit_cost = (line_cost / units).quantize(UNIT_COST_PLACES, rounding=ROUND_HALF_UP) if units else Decimal("0").quantize(UNIT_COST_PLACES)
        finished_rows.append(
            {
                "fg_sku": run["fg_sku"],
                "description": run["description"],
                "product_line": batch["product_line"],
                "abv_class": batch["abv_class"],
                "batch_id": batch["batch_id"],
                "container_sku": run["container_sku"],
                "units": units,
                "packaged_litres": litres,
                "beer_cost": beer,
                "packaging_material_cost": material_cost,
                "line_cost": line_cost,
                "unit_cost": unit_cost,
            }
        )

    total_batch_cost = money(brew_cost + packaging_material_total)
    total_packaged = sum(packaged_litres)
    finished = Decimal(batch["finished_litres"])
    brewed = Decimal(batch["brewed_litres"])
    volume_flag = "" if total_packaged == finished else "packaged volume does not match finished litres"
    yield_pct = (finished / brewed * Decimal("100")).quantize(CENTS, rounding=ROUND_HALF_UP) if brewed else Decimal("0.00")

    summary = {
        "batch_id": batch["batch_id"],
        "beer": batch["beer"],
        "product_line": batch["product_line"],
        "abv_class": batch["abv_class"],
        "brewed_litres": brewed,
        "finished_litres": finished,
        "yield_pct": yield_pct,
        "ingredient_cost": ing_total,
        "labour_cost": labour,
        "overhead_cost": overhead,
        "brew_cost": brew_cost,
        "packaging_material_cost": packaging_material_total,
        "total_batch_cost": total_batch_cost,
        "cost_per_finished_litre": cost_per_litre(brew_cost, finished),
        "volume_flag": volume_flag,
    }
    return summary, finished_rows


def cost_all(batches, ingredients_by_batch, runs_by_batch, wac):
    """Cost every batch. Returns (summaries, finished_rows)."""
    summaries = []
    finished = []
    for batch in batches:
        bid = batch["batch_id"]
        summary, rows = cost_batch(
            batch, ingredients_by_batch.get(bid, []), runs_by_batch.get(bid, []), wac
        )
        summaries.append(summary)
        finished.extend(rows)
    return summaries, finished
