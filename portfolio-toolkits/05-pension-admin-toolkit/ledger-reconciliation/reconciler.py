"""The comparison logic for the reconciliation tool.

Pure functions only: given two loaded ledgers, work out the status of every
Employee ID. No file access and no printing happen here.
"""

from decimal import Decimal
from dataclasses import dataclass

# Status labels, named once so the CLI and tests never disagree on spelling.
MATCHED = "Matched"
VARIANCE = "Variance"
MISSING_IN_TRUSTEE = "Missing in trustee"
MISSING_IN_INTERNAL = "Missing in internal"


@dataclass(frozen=True)
class ReconLine:
    """One Employee ID's outcome after comparison."""

    employee_id: str
    name: str
    internal_amount: Decimal
    trustee_amount: Decimal
    variance: Decimal
    status: str


def reconcile(internal, trustee, tolerance=Decimal("0.01")):
    """Compare two loaded ledgers and return a sorted list of ReconLine results.

    `internal` and `trustee` are the dicts returned by loader.load_ledger.
    A pair is Matched when the absolute variance is within tolerance, otherwise
    it is a Variance. Ids present on only one side are flagged as missing on the
    other side.
    """
    internal_records = internal["records"]
    trustee_records = trustee["records"]
    all_ids = sorted(set(internal_records) | set(trustee_records))

    lines = []
    for employee_id in all_ids:
        in_internal = employee_id in internal_records
        in_trustee = employee_id in trustee_records

        internal_amount = internal_records[employee_id]["amount"] if in_internal else Decimal("0")
        trustee_amount = trustee_records[employee_id]["amount"] if in_trustee else Decimal("0")
        name = internal_records[employee_id].get("name", "") if in_internal else ""

        if in_internal and not in_trustee:
            status = MISSING_IN_TRUSTEE
        elif in_trustee and not in_internal:
            status = MISSING_IN_INTERNAL
        else:
            variance = internal_amount - trustee_amount
            status = MATCHED if abs(variance) <= tolerance else VARIANCE

        variance = internal_amount - trustee_amount
        lines.append(
            ReconLine(
                employee_id=employee_id,
                name=name,
                internal_amount=internal_amount,
                trustee_amount=trustee_amount,
                variance=variance,
                status=status,
            )
        )
    return lines


def summarize(lines, internal, trustee):
    """Count outcomes for the report's summary line."""
    counts = {MATCHED: 0, VARIANCE: 0, MISSING_IN_TRUSTEE: 0, MISSING_IN_INTERNAL: 0}
    for line in lines:
        counts[line.status] += 1
    counts["duplicates"] = len(internal["duplicates"]) + len(trustee["duplicates"])
    counts["skipped"] = len(internal["skipped"]) + len(trustee["skipped"])
    return counts
