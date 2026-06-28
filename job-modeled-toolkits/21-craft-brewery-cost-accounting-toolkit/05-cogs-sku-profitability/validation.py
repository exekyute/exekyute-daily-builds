"""Validation for the COGS and margin tool.

Checks the sales lines against the finished-unit costs and against each other
before any margin is computed. The whole file is rejected if any check fails.
Each failure names the row and the problem.
"""

from decimal import Decimal, InvalidOperation

from margin import CHANNELS

SALES_COLUMNS = ("fg_sku", "channel", "units_sold", "unit_price")


class ValidationError(Exception):
    def __init__(self, problems):
        self.problems = problems
        super().__init__("\n".join(problems))


def _num(value):
    return Decimal(str(value).strip())


def validate(sales, header, basis):
    problems = []
    missing = [c for c in SALES_COLUMNS if c not in (header or [])]
    if missing:
        raise ValidationError(["missing required column(s): %s" % ", ".join(missing)])

    sold_by_sku = {}
    for index, row in enumerate(sales, start=2):
        where = "row %d" % index
        sku = (row.get("fg_sku") or "").strip()
        if sku not in basis:
            problems.append("%s: fg_sku %s was not produced this period" % (where, sku))

        channel = (row.get("channel") or "").strip()
        if channel not in CHANNELS:
            problems.append("%s: channel '%s' is not one of %s"
                            % (where, channel, ", ".join(CHANNELS)))

        try:
            units = _num(row.get("units_sold"))
            if units <= 0 or units != units.to_integral_value():
                problems.append("%s: units_sold must be a whole number greater than zero" % where)
            else:
                sold_by_sku[sku] = sold_by_sku.get(sku, Decimal("0")) + units
        except (InvalidOperation, ValueError, TypeError):
            problems.append("%s: units_sold is not a number" % where)

        try:
            if _num(row.get("unit_price")) <= 0:
                problems.append("%s: unit_price must be greater than zero" % where)
        except (InvalidOperation, ValueError, TypeError):
            problems.append("%s: unit_price is not a number" % where)

    # A SKU cannot sell more than it produced (there is no finished-goods opening).
    for sku, sold in sold_by_sku.items():
        if sku in basis and sold > basis[sku]["units_made"]:
            problems.append("%s: units sold %s exceed units produced %s"
                            % (sku, sold, basis[sku]["units_made"]))

    if problems:
        raise ValidationError(problems)
