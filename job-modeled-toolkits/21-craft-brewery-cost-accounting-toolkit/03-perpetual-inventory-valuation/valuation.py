"""Pure perpetual weighted-average valuation logic.

No file or console I/O lives here. Money is carried as decimal.Decimal and
quantized half up to the cent, never as float, so the ending inventory values
agree to the cent with the month-end close.

The ledger keeps a running quantity and dollar value for every SKU. A receipt or
opening balance raises both. An issue draws the value down at the current
weighted-average unit cost, the dollar balance divided by the quantity on hand.
This is the perpetual weighted-average method: the unit cost re-averages on every
receipt and stays put on every issue.
"""

from decimal import Decimal, ROUND_HALF_UP

CENTS = Decimal("0.01")
WAC_PLACES = Decimal("0.0001")  # weighted-average unit cost shown to 4 places

RECEIPT_TYPES = ("opening", "receipt")
CATEGORIES = ("raw_material", "packaging_material", "finished_goods")


def money(value):
    """Quantize a value to cents, rounding half up."""
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def issue_cost(on_hand_qty, on_hand_value, issue_qty):
    """Cost of an issue, valued at the current weighted-average unit cost."""
    on_hand_qty = Decimal(on_hand_qty)
    if on_hand_qty == 0:
        return Decimal("0.00")
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


def run_ledger(transactions):
    """Replay one SKU's transactions in file order and return its ending position.

    Each transaction is a dict with a txn_type, a Decimal quantity, and, for
    receipts and openings, a Decimal value (the dollars added). Issues take no
    value; they are costed at the running weighted-average. If on-hand quantity
    ever goes below zero the SKU is flagged, and processing continues so the bad
    data surfaces instead of hiding.
    """
    qty = Decimal("0")
    value = Decimal("0")
    flag = ""
    for txn in transactions:
        txn_type = txn["txn_type"]
        if txn_type in RECEIPT_TYPES:
            qty += Decimal(txn["quantity"])
            value = money(value + Decimal(txn["value"]))
        elif txn_type == "issue":
            cost = issue_cost(qty, value, txn["quantity"])
            qty -= Decimal(txn["quantity"])
            value = money(value - cost)
        if qty < 0:
            flag = "negative on-hand"
    return {
        "on_hand_qty": qty,
        "on_hand_value": value,
        "wac_unit_cost": weighted_average_unit_cost(qty, value),
        "integrity_flag": flag,
    }


def value_inventory(transactions):
    """Replay every SKU and return one ending row per SKU, in first-seen order.

    `transactions` is a flat list of dicts carrying sku, description, category,
    unit, txn_type, quantity, and value. Rows keep their file order within a SKU.
    """
    order = []
    groups = {}
    meta = {}
    for txn in transactions:
        sku = txn["sku"]
        if sku not in groups:
            groups[sku] = []
            order.append(sku)
            meta[sku] = {
                "description": txn["description"],
                "category": txn["category"],
                "unit": txn["unit"],
            }
        groups[sku].append(txn)

    rows = []
    for sku in order:
        ending = run_ledger(groups[sku])
        rows.append(
            {
                "sku": sku,
                "description": meta[sku]["description"],
                "category": meta[sku]["category"],
                "on_hand_qty": ending["on_hand_qty"],
                "unit": meta[sku]["unit"],
                "wac_unit_cost": ending["wac_unit_cost"],
                "inventory_value": ending["on_hand_value"],
                "integrity_flag": ending["integrity_flag"],
            }
        )
    return rows


def totals_by_category(rows):
    """Sum inventory value by category, plus a grand total."""
    by_cat = {}
    grand = Decimal("0")
    for row in rows:
        by_cat[row["category"]] = money(by_cat.get(row["category"], Decimal("0")) + row["inventory_value"])
        grand += row["inventory_value"]
    return by_cat, money(grand)
