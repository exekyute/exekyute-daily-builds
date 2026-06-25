# Spec: Collections Aging Dashboard

## Purpose
Load the aging report produced by the AR Aging and Late-Fee Engine, entirely in the browser, and
present a color-coded collections view: a per-invoice table plus the total outstanding per aging
bucket. The file is read with the FileReader API and never leaves the page, so a reviewer can scan
overdue accounts and priorities without any backend.

## Inputs
- An aging report CSV with this exact header:
  `invoice_number,customer,issue_date,due_date,amount,days_past_due,aging_bucket,late_fee,total_due`
- The user chooses the file through a file input. Reading is done locally with `FileReader`.

## Validation rules
- The header must match the expected columns. An empty file or a wrong header shows a clear message
  and renders nothing.
- A data row is skipped and counted when it has the wrong number of columns, a non-numeric amount,
  late fee, or total due, a non-numeric days-past-due, or an unrecognized bucket. The remaining rows
  still render.
- Money values are read as integer cents from the two-decimal strings, so totals never pick up
  floating-point artifacts.

## Logic
Pure functions live in `aging-logic.js` and take and return plain values (no DOM):

- `parseAgingCsv(text)` returns `{ rows, skipped, error }`.
- `dollarsToCents(text)` converts a money string to integer cents, or `null` when it is not a number.
- `bucketTotals(rows)` returns the count and total outstanding (sum of total due) per bucket, in the
  fixed order Current, 1-30, 31-60, 61-90, 90-plus.
- `grandTotalCents(rows)` sums total due across every row.
- `formatMoney(cents)` formats integer cents with `Intl.NumberFormat`.
- `bucketClass(bucket)` maps a bucket to its CSS class for color coding.

`dashboard.js` is a thin layer that reads the file, calls these functions, and renders the result.

## Outputs
- A table of invoices showing invoice number, customer, amount, days past due, aging bucket, late
  fee, and total due. Each row is color-coded by bucket.
- A summary of count and total outstanding per bucket, plus a grand total.
- A notice with the number of rows skipped, when any were malformed.

## Edge cases
- Empty file or wrong header: a friendly message, no crash, and no table.
- A malformed data row: skipped and counted while the valid rows still render. The seeded
  `sample-data/aging-report-malformed-sample.csv` has one short row and one non-numeric amount, so
  loading it shows 4 invoices and a "2 rows were skipped" notice.
- The seeded `sample-data/aging-report.csv` covers every bucket, so a single load shows the full
  color ramp and a complete summary.

## Hand-checked example
Loading `sample-data/aging-report.csv`, `INV-1004` shows days past due `90`, bucket `61-90`, late
fee `$15.00`, and total due `$1,015.00`. The per-bucket summary reads Current `$500.00`, 1-30
`$936.85`, 31-60 `$1,218.00`, 61-90 `$1,015.00`, 90-plus `$2,030.00`, grand total `$5,699.85`. These
match the AR Aging and Late-Fee Engine to the cent (see `../ar-aging-engine/spec.md`).

## Styling
- Two-tone palette defined as CSS variables: one base (slate) and one accent (red). Overdue buckets
  use the accent at increasing strength so severity reads as one escalating tone, with Current shown
  in a calm base tint.
- One spacing scale (multiples of 8px) reused for every margin, padding, and gap. Inputs, buttons,
  rows, and table cells get even, roomy padding, and elements align to a shared grid.
