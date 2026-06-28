"""Validation for the excise duty engine.

Checks the packaged-volume rows before any duty is computed. The whole file is
rejected if any row fails. Each failure names the row and the problem.
"""

from decimal import Decimal, InvalidOperation

from excise import ABV_CLASSES

REQUIRED_COLUMNS = ("fg_sku", "abv_class", "packaged_litres")


class ValidationError(Exception):
    def __init__(self, problems):
        self.problems = problems
        super().__init__("\n".join(problems))


def _num(value):
    return Decimal(str(value).strip())


def validate(rows, header, ytd_hectolitres):
    problems = []
    missing = [c for c in REQUIRED_COLUMNS if c not in (header or [])]
    if missing:
        raise ValidationError(["missing required column(s): %s" % ", ".join(missing)])

    try:
        if Decimal(str(ytd_hectolitres)) < 0:
            problems.append("--ytd-hl cannot be negative")
    except (InvalidOperation, ValueError, TypeError):
        problems.append("--ytd-hl '%s' is not a number" % ytd_hectolitres)

    for index, row in enumerate(rows, start=2):
        where = "row %d" % index
        if not (row.get("fg_sku") or "").strip():
            problems.append("%s: fg_sku is blank" % where)

        abv_class = (row.get("abv_class") or "").strip()
        if abv_class not in ABV_CLASSES:
            problems.append("%s: abv_class '%s' is not one of %s"
                            % (where, abv_class, ", ".join(ABV_CLASSES)))

        try:
            if _num(row.get("packaged_litres")) <= 0:
                problems.append("%s: packaged_litres must be greater than zero" % where)
        except (InvalidOperation, ValueError, TypeError):
            problems.append("%s: packaged_litres is not a number" % where)

    if problems:
        raise ValidationError(problems)
