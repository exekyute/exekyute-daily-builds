"""Validation for the procurement landed-cost engine.

Checks a list of raw purchase-order rows before any costing runs. The whole
file is rejected if any row fails, so a bad input never produces a half-correct
output CSV. Each failure names the row and the problem in plain language.
"""

from decimal import Decimal, InvalidOperation

from landed import CATEGORIES

REQUIRED_COLUMNS = (
    "po_id",
    "line_id",
    "date",
    "sku",
    "description",
    "category",
    "quantity",
    "unit",
    "unit_price",
    "freight_total",
    "duty_rate",
)


class ValidationError(Exception):
    """Raised with a list of human-readable problems."""

    def __init__(self, problems):
        self.problems = problems
        super().__init__("\n".join(problems))


def _decimal(value):
    return Decimal(str(value).strip())


def validate(rows, header):
    """Validate raw rows (dicts of strings). Raise ValidationError on any problem."""
    problems = []

    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ValidationError(["missing required column(s): %s" % ", ".join(missing)])

    seen_keys = set()
    po_freight = {}

    for index, row in enumerate(rows, start=2):  # row 1 is the header
        where = "row %d" % index
        line_id = (row.get("line_id") or "").strip()
        po_id = (row.get("po_id") or "").strip()

        if not po_id:
            problems.append("%s: po_id is blank" % where)
        if not line_id:
            problems.append("%s: line_id is blank" % where)

        key = (po_id, line_id)
        if po_id and line_id:
            if key in seen_keys:
                problems.append("%s: duplicate po_id/line_id %s/%s" % (where, po_id, line_id))
            seen_keys.add(key)

        if not (row.get("sku") or "").strip():
            problems.append("%s: sku is blank" % where)
        if not (row.get("unit") or "").strip():
            problems.append("%s: unit is blank" % where)

        category = (row.get("category") or "").strip()
        if category not in CATEGORIES:
            problems.append(
                "%s: category '%s' is not one of %s"
                % (where, category, ", ".join(CATEGORIES))
            )

        try:
            quantity = _decimal(row.get("quantity"))
            if quantity <= 0:
                problems.append("%s: quantity must be greater than zero" % where)
        except (InvalidOperation, ValueError, TypeError):
            problems.append("%s: quantity '%s' is not a number" % (where, row.get("quantity")))

        for field in ("unit_price", "freight_total", "duty_rate"):
            raw = row.get(field)
            try:
                value = _decimal(raw if (raw is not None and str(raw).strip() != "") else "0")
                if value < 0:
                    problems.append("%s: %s cannot be negative" % (where, field))
            except (InvalidOperation, ValueError, TypeError):
                problems.append("%s: %s '%s' is not a number" % (where, field, raw))

        # Freight is a per-order figure; every line of a PO must agree on it.
        raw_freight = row.get("freight_total")
        try:
            freight = _decimal(raw_freight if str(raw_freight).strip() != "" else "0")
            if po_id in po_freight and po_freight[po_id] != freight:
                problems.append(
                    "%s: freight_total %s disagrees with %s recorded earlier for %s"
                    % (where, freight, po_freight[po_id], po_id)
                )
            po_freight.setdefault(po_id, freight)
        except (InvalidOperation, ValueError, TypeError):
            pass  # already reported as non-numeric above

    if problems:
        raise ValidationError(problems)
