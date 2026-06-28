"""Validation for the batch production costing tool.

Checks the batch register, the ingredient lines, and the packaging runs against
each other and against the landed-cost file before any costing runs. The whole
run is rejected if any check fails, so a bad input never produces a half-correct
output. Each failure names where it is and what is wrong.
"""

from decimal import Decimal, InvalidOperation

ABV_CLASSES = ("over_2_5", "over_1_2_to_2_5", "not_over_1_2")

BATCH_COLUMNS = (
    "batch_id", "beer", "product_line", "abv_pct", "abv_class",
    "brewed_litres", "finished_litres", "labour_cost", "overhead_cost",
)
INGREDIENT_COLUMNS = ("batch_id", "material_sku", "quantity", "unit")
RUN_COLUMNS = (
    "batch_id", "fg_sku", "description", "container_sku", "label_sku",
    "units", "litres_per_unit",
)


class ValidationError(Exception):
    def __init__(self, problems):
        self.problems = problems
        super().__init__("\n".join(problems))


def _num(value):
    return Decimal(str(value).strip())


def _check_columns(header, required, name, problems):
    missing = [c for c in required if c not in (header or [])]
    if missing:
        problems.append("%s: missing column(s): %s" % (name, ", ".join(missing)))
    return not missing


def validate(batches, batch_header, ingredients, ing_header, runs, run_header, known_skus):
    problems = []
    ok = True
    ok &= _check_columns(batch_header, BATCH_COLUMNS, "batches.csv", problems)
    ok &= _check_columns(ing_header, INGREDIENT_COLUMNS, "batch_ingredients.csv", problems)
    ok &= _check_columns(run_header, RUN_COLUMNS, "packaging_runs.csv", problems)
    if not ok:
        raise ValidationError(problems)

    batch_ids = set()
    for index, row in enumerate(batches, start=2):
        where = "batches.csv row %d" % index
        bid = (row.get("batch_id") or "").strip()
        if not bid:
            problems.append("%s: batch_id is blank" % where)
        elif bid in batch_ids:
            problems.append("%s: duplicate batch_id %s" % (where, bid))
        batch_ids.add(bid)

        if (row.get("abv_class") or "").strip() not in ABV_CLASSES:
            problems.append("%s: abv_class '%s' is not one of %s"
                            % (where, row.get("abv_class"), ", ".join(ABV_CLASSES)))

        brewed = finished = None
        try:
            brewed = _num(row.get("brewed_litres"))
            if brewed <= 0:
                problems.append("%s: brewed_litres must be greater than zero" % where)
        except (InvalidOperation, ValueError, TypeError):
            problems.append("%s: brewed_litres is not a number" % where)
        try:
            finished = _num(row.get("finished_litres"))
            if finished <= 0:
                problems.append("%s: finished_litres must be greater than zero" % where)
        except (InvalidOperation, ValueError, TypeError):
            problems.append("%s: finished_litres is not a number" % where)
        if brewed is not None and finished is not None and finished > brewed:
            problems.append("%s: finished_litres %s exceeds brewed_litres %s (loss cannot be negative)"
                            % (where, finished, brewed))

        for field in ("labour_cost", "overhead_cost"):
            try:
                if _num(row.get(field)) < 0:
                    problems.append("%s: %s cannot be negative" % (where, field))
            except (InvalidOperation, ValueError, TypeError):
                problems.append("%s: %s is not a number" % (where, field))

    for index, row in enumerate(ingredients, start=2):
        where = "batch_ingredients.csv row %d" % index
        bid = (row.get("batch_id") or "").strip()
        sku = (row.get("material_sku") or "").strip()
        if bid not in batch_ids:
            problems.append("%s: batch_id %s is not in the batch register" % (where, bid))
        if sku not in known_skus:
            problems.append("%s: material_sku %s has no landed cost" % (where, sku))
        try:
            if _num(row.get("quantity")) <= 0:
                problems.append("%s: quantity must be greater than zero" % where)
        except (InvalidOperation, ValueError, TypeError):
            problems.append("%s: quantity is not a number" % where)

    for index, row in enumerate(runs, start=2):
        where = "packaging_runs.csv row %d" % index
        bid = (row.get("batch_id") or "").strip()
        container = (row.get("container_sku") or "").strip()
        label = (row.get("label_sku") or "").strip()
        if bid not in batch_ids:
            problems.append("%s: batch_id %s is not in the batch register" % (where, bid))
        if not (row.get("fg_sku") or "").strip():
            problems.append("%s: fg_sku is blank" % where)
        if container not in known_skus:
            problems.append("%s: container_sku %s has no landed cost" % (where, container))
        if label and label not in known_skus:
            problems.append("%s: label_sku %s has no landed cost" % (where, label))
        try:
            units = _num(row.get("units"))
            if units <= 0 or units != units.to_integral_value():
                problems.append("%s: units must be a whole number greater than zero" % where)
        except (InvalidOperation, ValueError, TypeError):
            problems.append("%s: units is not a number" % where)
        try:
            if _num(row.get("litres_per_unit")) <= 0:
                problems.append("%s: litres_per_unit must be greater than zero" % where)
        except (InvalidOperation, ValueError, TypeError):
            problems.append("%s: litres_per_unit is not a number" % where)

    if problems:
        raise ValidationError(problems)
