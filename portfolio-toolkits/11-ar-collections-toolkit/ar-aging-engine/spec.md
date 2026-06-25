# Spec: AR Aging and Late-Fee Engine

## Purpose
Read a CSV of open invoices and produce a per-invoice aging report. For each invoice the engine
computes days past due against a reference date, assigns an aging bucket, and applies a policy late
fee to overdue invoices. Bad rows are rejected with a plain-language reason and never written to the
report, so the output stays accurate and auditable and overdue accounts can be prioritized.

## Inputs
- An open-invoices CSV with this exact header:
  `invoice_number,customer,issue_date,due_date,amount`
- Command-line options:
  - `--input PATH` (default `sample-data/open-invoices.csv`)
  - `--output PATH` (default `sample-data/aging-report.csv`)
  - `--reference-date YYYY-MM-DD` (default today)
  - `--rate DECIMAL` late-fee rate, where `0.015` means 1.5% (default `0.015`)

## Validation rules
A row that fails any rule is rejected, recorded with a reason, and left out of the report. The
remaining valid rows are still processed.

- The row must have exactly 5 fields (a missing field or an extra field is rejected).
- `invoice_number` must be present and unique. The first occurrence is kept; a later duplicate is rejected.
- `customer` must be present.
- `issue_date` and `due_date` must parse as `YYYY-MM-DD`, and `due_date` must not be before `issue_date`.
- `amount` must be a number greater than 0 (zero, negative, or non-numeric is rejected).
- The header must match the expected columns, or the run stops with an error.
- `--rate` must be 0 or greater; `--reference-date` must be a valid date.

## Logic
1. Validate the header, then validate each data row into an invoice or a reject.
2. Days past due: `days_past_due = reference_date - due_date` in whole days. Zero or negative means
   the invoice is not yet overdue.
3. Aging bucket by inclusive day ranges:

   | Bucket   | Days past due |
   |----------|---------------|
   | Current  | 0 or less     |
   | 1-30     | 1 to 30       |
   | 31-60    | 31 to 60      |
   | 61-90    | 61 to 90      |
   | 90-plus  | 91 or more    |

4. Late fee: `amount * rate`, charged only when `days_past_due` is 1 or more, rounded to the cent
   with `ROUND_HALF_UP`. Current invoices are charged `0.00`.
5. Total due: `amount + late_fee`.

All money is handled with `decimal.Decimal` and printed as fixed-point values, never scientific notation.

## Outputs
- An aging report CSV with this header:
  `invoice_number,customer,issue_date,due_date,amount,days_past_due,aging_bucket,late_fee,total_due`
- A summary printed to standard output: count and total outstanding (amount plus late fee) per
  bucket, plus a grand total and the number of rejected rows.
- Rejected rows printed to standard error with their line number and reason.
- Exit code `0` when every row is valid, `1` when one or more rows were rejected (the valid rows are
  still written), `2` for a missing file or a bad header.

## Edge cases
The seeded `sample-data/open-invoices.csv` exercises each branch in a single run:

- A current invoice due in the future (`INV-1001`, days past due `-33`, fee `0.00`).
- One invoice in each overdue bucket: `INV-1002` (1-30), `INV-1010` (31-60), `INV-1004` (61-90),
  `INV-1005` (90-plus).
- Boundary invoices exactly on a bucket edge: `INV-1003` at `30` days stays in `1-30`, and `INV-1004`
  at `90` days stays in `61-90`.
- A row with a missing field (`INV-2001`) and a row with an extra field (`INV-2002`), both rejected.
- A duplicate invoice number (`INV-1002` a second time), rejected.
- A zero amount (`INV-2003`) and a negative amount (`INV-2004`), both rejected.

## Hand-checked example
`INV-1004`, amount `1000.00`, due `2026-03-14`, reference date `2026-06-12`:

- Days past due: 2026-03-14 to 2026-06-12 is `90` days.
- Bucket: `90` falls in `61-90`.
- Late fee: `1000.00 * 0.015 = 15.00`.
- Total due: `1000.00 + 15.00 = 1015.00`.

The Collections Aging Dashboard reads the same report and shows `INV-1004` with days past due `90`,
bucket `61-90`, and late fee `$15.00`, matching this engine to the cent.
