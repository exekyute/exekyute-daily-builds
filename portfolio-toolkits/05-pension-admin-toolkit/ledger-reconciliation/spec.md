# Spec: Ledger Reconciliation Tool

## Purpose

Compare an internal payroll register against a third-party trustee file by Employee ID and
produce a variance report. This models the day-to-day reconciliation work of confirming that
the amounts an employer records match the amounts the trustee holds.

## Inputs

- `--internal`: path to `internal_payroll.csv` with an `employee_id,name,amount` header.
- `--trustee`: path to `trustee_assets.csv` with an `employee_id,amount` header.
- `--tolerance`: optional maximum absolute difference still treated as a match (default `0.01`).
- `--report`: optional output path for the CSV report (default `variance_report.csv`).

## Validation rules

- Both files must contain their required columns. A missing column is a clear, immediate error.
- Every amount must be numeric. Rows with a blank or non-numeric amount are skipped and counted,
  not crashed on.
- Employee IDs must be non-empty. Rows with a blank ID are skipped and counted.
- A duplicate Employee ID within a file is recorded as a finding. The first occurrence is kept;
  the repeat does not overwrite it.

## Logic

1. Load each file into a dictionary keyed by Employee ID, capturing duplicates and skipped rows.
2. For every ID seen in either file, classify it:
   - **Matched**: present in both, absolute variance within tolerance.
   - **Variance**: present in both, absolute variance above tolerance.
   - **Missing in trustee**: present in internal only.
   - **Missing in internal**: present in trustee only.
3. Variance = internal amount minus trustee amount (signed), computed with `Decimal`.

## Outputs

- A markdown variance table printed to the screen: Employee ID, Name, Internal, Trustee,
  Variance, Status.
- A summary line counting matched / variance / missing-each-side / duplicates / skipped rows.
- The same table written to a CSV report file for the record.

## Edge cases

- An ID present in only one file (flagged as missing on the other side).
- A duplicate ID within a file (recorded, not merged).
- A non-numeric or blank amount (row skipped and counted).
- A difference of exactly the tolerance (treated as a match).
- An empty file (no records, reported cleanly).

## Sample data design

The included synthetic files are seeded so the report exercises every path:

- `E001` matches exactly.
- `E002` has a real variance ($25.50).
- `E003` matches, and also appears twice in the internal file (a duplicate).
- `E004` matches exactly.
- `E005` exists only in internal (missing in trustee).
- `E006` differs by exactly $0.01 (within tolerance, so matched).
- `E007` exists only in the trustee file (missing in internal).
