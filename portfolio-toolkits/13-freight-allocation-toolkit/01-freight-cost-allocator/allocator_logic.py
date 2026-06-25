"""Pure business logic for the Freight Cost Allocator.

This module holds parsing, validation, and allocation logic only. It performs no
file reading, no printing, and no argument parsing. The thin CLI wrapper in
cli.py is responsible for all input and output. Keeping the logic pure makes it
straightforward to unit test every rule and branch.

Money is handled with decimal.Decimal and ROUND_HALF_UP. The actual allocation
runs in integer cents and uses the largest-remainder method so the per-line
allocations always sum back to the freight total exactly, with no cent lost or
gained.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

# The columns every shipment line-items CSV must provide.
REQUIRED_COLUMNS = ["line_id", "description", "quantity", "unit_cost", "weight"]

# Allocation bases the tool understands.
VALID_BASES = ("weight", "value")

# Key DictReader uses to collect any fields beyond the header (extra columns).
EXTRA_KEY = "_extra"


@dataclass
class LineItem:
    """One validated shipment line.

    quantity is a positive integer. unit_cost and weight are non-negative
    Decimal values. The extended value (quantity * unit_cost) is used by the
    value basis and is computed on demand rather than stored, so it can never
    drift from quantity and unit_cost.
    """

    line_id: str
    description: str
    quantity: int
    unit_cost: Decimal
    weight: Decimal

    def value(self):
        """Extended line value: quantity multiplied by unit cost."""
        return self.unit_cost * self.quantity

    def basis_amount(self, basis):
        """Return the amount used to weight this line for the given basis."""
        if basis == "weight":
            return self.weight
        return self.value()


class ValidationError(Exception):
    """Raised when input fails validation.

    Carries the full list of problems so the caller can report every issue at
    once rather than stopping at the first one.
    """

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


def missing_columns(fieldnames):
    """Return the required columns absent from a CSV header, in order.

    fieldnames is the list of header names (or None if the file had no header).
    """
    present = set(fieldnames or [])
    return [column for column in REQUIRED_COLUMNS if column not in present]


def _parse_decimal(raw):
    """Parse a money or weight string into a Decimal.

    Raises ValueError on blank or non-numeric input so the caller can attach a
    line number and column name to the message.
    """
    if raw is None:
        raise ValueError("missing value")
    text = raw.strip()
    if text == "":
        raise ValueError("missing value")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError("not a number")


def _parse_quantity(raw):
    """Parse a positive integer quantity.

    Rejects blanks, non-integers, and values that are zero or negative.
    """
    if raw is None or str(raw).strip() == "":
        raise ValueError("missing value")
    text = str(raw).strip()
    try:
        value = int(text)
    except ValueError:
        raise ValueError("not a whole number")
    if value <= 0:
        raise ValueError("must be greater than 0")
    return value


def build_line_items(rows):
    """Validate raw CSV rows and build LineItem objects.

    rows is a list of (line_number, record) tuples, where record is a dict keyed
    by column name (as produced by csv.DictReader). line_number is the 1-based
    line in the source file, so messages point at the row the reader can see.

    Returns a list of LineItem on success. Raises ValidationError with every
    problem found if any row is invalid or line_id is not unique.
    """
    problems = []
    items = []
    seen_ids = {}

    if not rows:
        raise ValidationError(["The file has no data rows."])

    for line_number, record in rows:
        row_problems = []

        # An extra field beyond the header lands under EXTRA_KEY.
        extra = record.get(EXTRA_KEY)
        if extra:
            row_problems.append(
                "has more fields than the header (unexpected extra value)"
            )

        line_id = (record.get("line_id") or "").strip()
        description = (record.get("description") or "").strip()

        if line_id == "":
            row_problems.append("line_id is required")

        try:
            quantity = _parse_quantity(record.get("quantity"))
        except ValueError as error:
            quantity = None
            row_problems.append("quantity {0}".format(error))

        try:
            unit_cost = _parse_decimal(record.get("unit_cost"))
            if unit_cost < 0:
                row_problems.append("unit_cost must be 0 or greater")
                unit_cost = None
        except ValueError as error:
            unit_cost = None
            row_problems.append("unit_cost {0}".format(error))

        try:
            weight = _parse_decimal(record.get("weight"))
            if weight < 0:
                row_problems.append("weight must be 0 or greater")
                weight = None
        except ValueError as error:
            weight = None
            row_problems.append("weight {0}".format(error))

        # Track duplicate line ids across the whole file.
        if line_id != "":
            if line_id in seen_ids:
                row_problems.append(
                    "duplicate line_id (first seen on line {0})".format(
                        seen_ids[line_id]
                    )
                )
            else:
                seen_ids[line_id] = line_number

        if row_problems:
            for problem in row_problems:
                problems.append("Line {0}: {1}.".format(line_number, problem))
            continue

        items.append(
            LineItem(
                line_id=line_id,
                description=description,
                quantity=quantity,
                unit_cost=unit_cost,
                weight=weight,
            )
        )

    if problems:
        raise ValidationError(problems)

    return items


def to_cents(amount):
    """Round a Decimal dollar amount to whole cents using ROUND_HALF_UP."""
    cents = (amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def parse_freight_cents(raw):
    """Parse the freight charge (in dollars) into integer cents.

    Raises ValidationError on blank, non-numeric, or negative input.
    """
    try:
        amount = _parse_decimal(raw)
    except ValueError as error:
        raise ValidationError(["Freight charge {0}.".format(error)])
    if amount < 0:
        raise ValidationError(["Freight charge must be 0 or greater."])
    return to_cents(amount)


def allocate(line_items, freight_cents, basis):
    """Allocate freight across line items using the largest-remainder method.

    Returns a list of allocations in integer cents, one per line item, in the
    same order as line_items. The allocations always sum to freight_cents
    exactly.

    The basis must be "weight" or "value". A ValidationError is raised if the
    basis total across all lines is not positive, since freight cannot be shared
    out when every line has zero weight (or zero value).
    """
    if basis not in VALID_BASES:
        raise ValidationError(
            ["Basis must be one of: {0}.".format(", ".join(VALID_BASES))]
        )

    amounts = [item.basis_amount(basis) for item in line_items]
    total = sum(amounts, Decimal(0))

    if total <= 0:
        raise ValidationError(
            [
                "Cannot allocate by {0}: the total {0} across all lines is 0.".format(
                    basis
                )
            ]
        )

    # Exact share per line, then split into a floor part and a fractional
    # remainder. Every value here is non-negative, so int() truncation equals
    # the floor.
    floors = []
    remainders = []
    for amount in amounts:
        exact = (Decimal(freight_cents) * amount) / total
        floor = int(exact)
        floors.append(floor)
        remainders.append(exact - floor)

    leftover = freight_cents - sum(floors)

    # Hand the leftover cents to the lines with the largest remainder. Ties are
    # broken by original order so the result is deterministic. Because the
    # remainders sum to the (integer) leftover and each is below 1, there are
    # always strictly more positive-remainder lines than leftover cents, so a
    # zero-basis line never receives a cent.
    order = sorted(
        range(len(line_items)),
        key=lambda i: (remainders[i], -i),
        reverse=True,
    )

    allocations = list(floors)
    for i in order[:leftover]:
        allocations[i] += 1

    return allocations


def landed_unit_cost_cents(item, allocation_cents):
    """Per-unit landed cost in cents: unit cost plus freight spread over units.

    Rounded to the cent with ROUND_HALF_UP. This is a display figure. Exact
    reconciliation is done on the allocation and the line value, not on this
    rounded per-unit number.
    """
    unit_cost_cents = to_cents(item.unit_cost)
    freight_per_unit = (Decimal(allocation_cents) / item.quantity).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return unit_cost_cents + int(freight_per_unit)


def format_cents(cents):
    """Format integer cents as a fixed-point dollar string, e.g. 2593 -> '25.93'.

    Never uses scientific notation and always shows exactly two decimal places.
    """
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return "{0}{1}.{2:02d}".format(sign, whole, fraction)


def build_landed_rows(line_items, allocations):
    """Build the landed-cost output rows as lists of strings.

    Returns (header, rows) ready to write to CSV. Money columns are fixed-point
    two-place strings.
    """
    header = [
        "line_id",
        "description",
        "quantity",
        "unit_cost",
        "allocated_freight",
        "landed_unit_cost",
    ]
    rows = []
    for item, allocation in zip(line_items, allocations):
        rows.append(
            [
                item.line_id,
                item.description,
                str(item.quantity),
                format_cents(to_cents(item.unit_cost)),
                format_cents(allocation),
                format_cents(landed_unit_cost_cents(item, allocation)),
            ]
        )
    return header, rows
