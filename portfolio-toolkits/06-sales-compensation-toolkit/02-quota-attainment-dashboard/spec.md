# Spec: Quota Attainment Dashboard

## Purpose

Load a CSV of rep results and show, at a glance, who landed under, at, or over
quota. The page reads the file in the browser, checks every row, bands each rep
by attainment, and summarises the team. Rows with a problem are reported on
their own rather than aborting the whole file, so one bad row never hides the
good ones and a reviewer can see exactly what to fix.

## Inputs

- A CSV file, chosen with the file picker and read in the browser with the
  `FileReader` API. Nothing is sent anywhere.
- Required columns, matched by name in the header (case-insensitive):
  `rep_id`, `rep_name`, `quota`, `actual_revenue`. Extra columns in the header
  are allowed and ignored.
- Money values may include `$`, commas, and spaces.

Sample files: `data/sample_results.csv` (clean) and `data/messy_results.csv`
(carries one of every row-level problem).

## Validation rules

**Whole-file checks** stop the load with a single message:

- The file is not empty.
- The header contains every required column. A missing column is named.

**Row-level checks** do not stop the load. A failing row is left out of the
table and listed in the issues panel with its line number and reason:

- The row has the same number of fields as the header (catches a missing field
  and an extra field).
- `rep_id` is present and not a duplicate of an earlier row.
- `rep_name` is present.
- `quota` parses as a number and is greater than 0.
- `actual_revenue` parses as a number and is 0 or greater.

## Logic

All money is handled in integer cents. For each valid row:

- `attainment = actual_revenue / quota`, computed from the integer cents.
- The rep is banded by comparing cents directly:
  - **over** when `actual > quota`,
  - **at** when `actual == quota`,
  - **under** when `actual < quota`.

The summary counts reps in each band and totals quota and actual across the
valid rows, with an overall attainment for the team. Money prints with
`Intl.NumberFormat` as currency and attainment as a percent to one decimal
place.

## Outputs

- A team summary: counts of reps over, at, and under quota, the number of rows
  with issues, and a line with team totals and overall attainment.
- A color-coded table of valid reps: green for over, amber for at, red for
  under, each with a matching status badge.
- An issues panel listing every rejected row by line number and reason. It is
  hidden when there are none.

## Edge cases

- **Boundary at exactly 100%.** A rep whose actual equals quota is banded **at**,
  not over or under. In `sample_results.csv`, Carmen Diaz at `$100,000` of
  `$100,000` lands exactly at quota.
- **Just under and just over.** David Eze at `99.9%` reads as under; Elena Frost
  at `101.0%` reads as over. The band follows a strict cents comparison, so a
  single cent decides the boundary.
- **One file, every problem.** `messy_results.csv` keeps three valid reps in the
  table (one over, one at, one under) while the issues panel shows a missing
  field, an extra field, a duplicate `rep_id`, a zero quota, and a non-numeric
  quota, all from a single load.
- **Bad header.** A file missing `actual_revenue` is refused with a message that
  names the missing column, instead of producing a half-built table.
