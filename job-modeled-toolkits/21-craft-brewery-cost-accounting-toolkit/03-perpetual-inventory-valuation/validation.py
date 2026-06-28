"""Validation for the perpetual inventory valuation tool.

Checks the transaction ledger before any valuation runs. The whole file is
rejected if any row fails, so a bad ledger never produces a half-correct
valuation. Each failure names the row and the problem.
"""

from decimal import Decimal, InvalidOperation

from valuation import CATEGORIES, RECEIPT_TYPES

TXN_TYPES = RECEIPT_TYPES + ("issue",)

REQUIRED_COLUMNS = (
    "txn_id", "date", "sku", "description", "category", "txn_type",
    "quantity", "unit", "value",
)


class ValidationError(Exception):
    def __init__(self, problems):
        self.problems = problems
        super().__init__("\n".join(problems))


def _num(value):
    return Decimal(str(value).strip())


def validate(rows, header):
    problems = []
    missing = [c for c in REQUIRED_COLUMNS if c not in (header or [])]
    if missing:
        raise ValidationError(["missing required column(s): %s" % ", ".join(missing)])

    seen = set()
    for index, row in enumerate(rows, start=2):
        where = "row %d" % index
        txn_id = (row.get("txn_id") or "").strip()
        if not txn_id:
            problems.append("%s: txn_id is blank" % where)
        elif txn_id in seen:
            problems.append("%s: duplicate txn_id %s" % (where, txn_id))
        seen.add(txn_id)

        if not (row.get("sku") or "").strip():
            problems.append("%s: sku is blank" % where)
        if not (row.get("unit") or "").strip():
            problems.append("%s: unit is blank" % where)

        category = (row.get("category") or "").strip()
        if category not in CATEGORIES:
            problems.append("%s: category '%s' is not one of %s"
                            % (where, category, ", ".join(CATEGORIES)))

        txn_type = (row.get("txn_type") or "").strip()
        if txn_type not in TXN_TYPES:
            problems.append("%s: txn_type '%s' is not one of %s"
                            % (where, txn_type, ", ".join(TXN_TYPES)))

        try:
            if _num(row.get("quantity")) <= 0:
                problems.append("%s: quantity must be greater than zero" % where)
        except (InvalidOperation, ValueError, TypeError):
            problems.append("%s: quantity is not a number" % where)

        raw_value = (row.get("value") or "").strip()
        if txn_type in RECEIPT_TYPES:
            try:
                if _num(raw_value or "0") < 0:
                    problems.append("%s: value cannot be negative" % where)
                if raw_value == "":
                    problems.append("%s: a %s needs a value" % (where, txn_type))
            except (InvalidOperation, ValueError, TypeError):
                problems.append("%s: value is not a number" % where)

    if problems:
        raise ValidationError(problems)
