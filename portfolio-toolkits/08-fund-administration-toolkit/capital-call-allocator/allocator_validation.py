"""Input checks for the capital call allocator.

These functions decide whether the inputs are safe to allocate. They do not read
files or print anything. Each function returns the cleaned value (when valid)
together with a list of plain-language error messages.

The checks collect every problem they find rather than stopping at the first
one, so a person can fix all the bad rows in a single pass.
"""

from decimal import Decimal, InvalidOperation

EXPECTED_HEADER = ["investor", "commitment"]


def validate_call_total(raw):
    """Check the call total typed on the command line.

    Returns (Decimal, errors). The Decimal is None when the value cannot be used.
    """
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        return None, [f"Call total '{raw}' is not a valid number."]

    if value <= 0:
        return None, [f"Call total must be greater than zero (got {value})."]

    return value, []


def validate_commitments(header, rows):
    """Check the parsed commitments file.

    Arguments:
        header: the list of column names from the first CSV line, or None if the
            file held no rows at all.
        rows: the remaining lines, each a list of raw string fields.

    Returns (commitments, errors). commitments is a list of (name, Decimal) pairs
    and is only meaningful when errors is empty.
    """
    errors = []

    if header is None:
        return [], ["The commitments file is empty."]

    if [column.strip().lower() for column in header] != EXPECTED_HEADER:
        errors.append(
            "Header must be exactly 'investor,commitment' "
            f"(found '{','.join(header)}')."
        )

    if not rows:
        errors.append("The commitments file has a header but no investor rows.")

    commitments = []
    first_seen = {}
    for index, fields in enumerate(rows):
        line_number = index + 2  # +1 for the header, +1 for 1-based counting

        if len(fields) != 2:
            errors.append(
                f"Line {line_number}: expected 2 fields (investor, commitment) "
                f"but found {len(fields)}."
            )
            continue

        name = fields[0].strip()
        commitment_text = fields[1].strip()

        if name == "":
            errors.append(f"Line {line_number}: investor name is blank.")
            continue

        try:
            commitment = Decimal(commitment_text)
        except (InvalidOperation, ValueError):
            errors.append(
                f"Line {line_number}: commitment '{commitment_text}' "
                "is not a valid number."
            )
            continue

        if commitment < 0:
            errors.append(
                f"Line {line_number}: commitment may not be negative (got {commitment})."
            )
            continue

        if name in first_seen:
            errors.append(
                f"Line {line_number}: duplicate investor '{name}' "
                f"(first seen on line {first_seen[name]})."
            )
            continue

        first_seen[name] = line_number
        commitments.append((name, commitment))

    # Only worth checking the fund-level total once the individual rows are clean.
    if not errors:
        total = sum(commitment for _, commitment in commitments)
        if total <= 0:
            errors.append(
                "Total commitment across all investors must be greater than zero."
            )

    return commitments, errors
