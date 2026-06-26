"""Input validation for the costing engine.

Every check returns a plain-language message naming the row and the problem, so
a bad transaction file is rejected with something a person can act on rather
than a stack trace.
"""

from decimal import Decimal, InvalidOperation

from costing import ABV_CLASSES, RECEIPT_TYPES

REQUIRED_COLUMNS = [
    "txn_id",
    "date",
    "sku",
    "description",
    "category",
    "txn_type",
    "quantity",
    "unit",
    "unit_price",
    "freight",
    "customs_duty",
    "abv_class",
    "litres_per_unit",
]

CATEGORIES = ("raw_material", "packaging_material", "finished_goods")
TXN_TYPES = ("opening", "receipt", "package", "issue")


def _to_decimal(raw):
    """Parse a possibly blank money or quantity field, treating blank as zero."""
    text = (raw or "").strip()
    if text == "":
        return Decimal("0")
    return Decimal(text)


def validate_header(fieldnames):
    """Confirm the file carries exactly the columns the engine expects."""
    errors = []
    missing = [c for c in REQUIRED_COLUMNS if c not in (fieldnames or [])]
    if missing:
        errors.append("Missing required column(s): %s." % ", ".join(missing))
    return errors


def validate_rows(rows):
    """Check every row. Returns a list of error strings, empty when the file is clean."""
    errors = []
    seen_ids = set()

    for line_no, row in enumerate(rows, start=2):  # line 1 is the header
        txn_id = (row.get("txn_id") or "").strip()
        where = "Row %d" % line_no
        if txn_id:
            where = "Row %d (txn %s)" % (line_no, txn_id)

        if not txn_id:
            errors.append("%s: txn_id is blank." % where)
        elif txn_id in seen_ids:
            errors.append("%s: duplicate txn_id." % where)
        else:
            seen_ids.add(txn_id)

        if not (row.get("sku") or "").strip():
            errors.append("%s: sku is blank." % where)
        if not (row.get("unit") or "").strip():
            errors.append("%s: unit is blank." % where)

        category = (row.get("category") or "").strip()
        if category not in CATEGORIES:
            errors.append(
                "%s: category '%s' is not one of %s."
                % (where, category, ", ".join(CATEGORIES))
            )

        txn_type = (row.get("txn_type") or "").strip()
        if txn_type not in TXN_TYPES:
            errors.append(
                "%s: txn_type '%s' is not one of %s."
                % (where, txn_type, ", ".join(TXN_TYPES))
            )

        try:
            quantity = _to_decimal(row.get("quantity"))
            if quantity <= 0:
                errors.append("%s: quantity must be greater than zero." % where)
        except InvalidOperation:
            errors.append("%s: quantity '%s' is not a number." % (where, row.get("quantity")))

        for field in ("unit_price", "freight", "customs_duty", "litres_per_unit"):
            value = (row.get(field) or "").strip()
            if value == "":
                continue
            try:
                if _to_decimal(value) < 0:
                    errors.append("%s: %s cannot be negative." % (where, field))
            except InvalidOperation:
                errors.append("%s: %s '%s' is not a number." % (where, field, value))

        if txn_type in RECEIPT_TYPES:
            if (row.get("unit_price") or "").strip() == "":
                errors.append("%s: %s needs a unit_price." % (where, txn_type))

        if txn_type == "opening":
            for field in ("freight", "customs_duty"):
                value = (row.get(field) or "").strip()
                if value not in ("", "0", "0.0", "0.00"):
                    errors.append(
                        "%s: an opening balance cannot carry %s." % (where, field)
                    )

        if txn_type == "package":
            abv_class = (row.get("abv_class") or "").strip()
            if abv_class not in ABV_CLASSES:
                errors.append(
                    "%s: package needs an abv_class of %s."
                    % (where, ", ".join(ABV_CLASSES))
                )
            litres = (row.get("litres_per_unit") or "").strip()
            if litres == "":
                errors.append("%s: package needs litres_per_unit." % where)
            else:
                try:
                    if _to_decimal(litres) <= 0:
                        errors.append(
                            "%s: litres_per_unit must be greater than zero." % where
                        )
                except InvalidOperation:
                    pass  # numeric check above already reported it
        else:
            if (row.get("abv_class") or "").strip():
                errors.append(
                    "%s: abv_class only belongs on a package transaction." % where
                )

    return errors
