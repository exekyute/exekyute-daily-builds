"""Input validation for the fixed-asset engine.

Each raw CSV row is checked here before any depreciation is calculated. A row
that breaks a rule is rejected with a clear message naming the asset, the field,
and what was expected, so a bad register is caught at the door rather than
producing wrong numbers.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from cca import CCA_RATES

ASSET_FIELDS = [
    "asset_id",
    "description",
    "cca_class",
    "capital_cost",
    "in_service_date",
    "useful_life_years",
    "salvage_value",
    "disposed",
    "disposal_proceeds",
    "prior_accum_book_dep",
]


class ValidationError(Exception):
    """Raised when a row fails a validation rule."""


def _decimal(value, field, asset_id):
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValidationError(
            "Asset %s: %s must be a number, got %r" % (asset_id, field, value)
        )


def validate_asset_row(row):
    """Validate one asset row and return it parsed into typed values.

    Money fields become Decimal, the year is pulled from the in-service date,
    and the disposed flag becomes a bool. Raises ValidationError on the first
    rule a row breaks.
    """
    missing = [f for f in ASSET_FIELDS if f not in row or str(row[f]).strip() == ""]
    # disposal_proceeds is allowed to be blank for an asset that was not disposed.
    asset_id = str(row.get("asset_id", "")).strip() or "(missing id)"
    disposed_raw = str(row.get("disposed", "")).strip().upper()

    real_missing = [f for f in missing if not (f == "disposal_proceeds" and disposed_raw == "N")]
    if real_missing:
        raise ValidationError(
            "Asset %s: missing required field(s): %s" % (asset_id, ", ".join(real_missing))
        )

    cca_class = str(row["cca_class"]).strip()
    if cca_class not in CCA_RATES:
        raise ValidationError(
            "Asset %s: unknown CCA class %r, expected one of %s"
            % (asset_id, cca_class, ", ".join(sorted(CCA_RATES)))
        )

    capital_cost = _decimal(row["capital_cost"], "capital_cost", asset_id)
    if capital_cost < Decimal("0"):
        raise ValidationError("Asset %s: capital_cost cannot be negative" % asset_id)

    salvage_value = _decimal(row["salvage_value"], "salvage_value", asset_id)
    if salvage_value < Decimal("0"):
        raise ValidationError("Asset %s: salvage_value cannot be negative" % asset_id)
    if salvage_value > capital_cost:
        raise ValidationError(
            "Asset %s: salvage_value cannot exceed capital_cost" % asset_id
        )

    try:
        useful_life_years = int(str(row["useful_life_years"]).strip())
    except ValueError:
        raise ValidationError(
            "Asset %s: useful_life_years must be a whole number" % asset_id
        )
    if useful_life_years <= 0:
        raise ValidationError(
            "Asset %s: useful_life_years must be greater than zero" % asset_id
        )

    try:
        in_service = datetime.strptime(str(row["in_service_date"]).strip(), "%Y-%m-%d")
    except ValueError:
        raise ValidationError(
            "Asset %s: in_service_date must be in YYYY-MM-DD format, got %r"
            % (asset_id, row["in_service_date"])
        )

    if disposed_raw not in ("Y", "N"):
        raise ValidationError(
            "Asset %s: disposed must be Y or N, got %r" % (asset_id, row["disposed"])
        )
    disposed = disposed_raw == "Y"

    if disposed:
        disposal_proceeds = _decimal(row["disposal_proceeds"], "disposal_proceeds", asset_id)
        if disposal_proceeds < Decimal("0"):
            raise ValidationError(
                "Asset %s: disposal_proceeds cannot be negative" % asset_id
            )
    else:
        disposal_proceeds = Decimal("0")

    prior_accum = _decimal(row["prior_accum_book_dep"], "prior_accum_book_dep", asset_id)
    if prior_accum < Decimal("0"):
        raise ValidationError(
            "Asset %s: prior_accum_book_dep cannot be negative" % asset_id
        )
    if prior_accum > (capital_cost - salvage_value):
        raise ValidationError(
            "Asset %s: prior_accum_book_dep cannot exceed cost less salvage" % asset_id
        )

    return {
        "asset_id": asset_id,
        "description": str(row["description"]).strip(),
        "cca_class": cca_class,
        "capital_cost": capital_cost,
        "in_service_date": str(row["in_service_date"]).strip(),
        "in_service_year": in_service.year,
        "useful_life_years": useful_life_years,
        "salvage_value": salvage_value,
        "disposed": disposed,
        "disposal_proceeds": disposal_proceeds,
        "prior_accum_book_dep": prior_accum,
    }


def validate_opening_row(row):
    """Validate one opening-UCC row and return (class, Decimal opening UCC)."""
    cca_class = str(row.get("cca_class", "")).strip()
    if cca_class not in CCA_RATES:
        raise ValidationError(
            "Opening UCC: unknown CCA class %r, expected one of %s"
            % (cca_class, ", ".join(sorted(CCA_RATES)))
        )
    opening = _decimal(row.get("opening_ucc", ""), "opening_ucc", "class " + cca_class)
    if opening < Decimal("0"):
        raise ValidationError(
            "Opening UCC for class %s cannot be negative" % cca_class
        )
    return cca_class, opening
