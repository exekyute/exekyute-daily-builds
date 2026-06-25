# Spec: Renewal Pipeline Tracker

## Purpose

Load the renewals CSV the scheduler produces and show the renewal pipeline at a
glance. The page reads the file in the browser, validates every row, counts the
leases by status, and renders a table that can be sorted by any key column so the
analyst can work the most urgent leases first. Nothing is sent anywhere.

## Inputs

- A renewals CSV, chosen with the file picker and read in the browser with the
  `FileReader` API. Default sample: `data/renewals.csv`, the file the scheduler in
  `03-lease-renewal-escalation-scheduler` writes.
- Required columns, matched by name in the header (case-insensitive); extra columns
  are allowed and ignored: `unit`, `tenant`, `current_rent`, `lease_end`,
  `renewal_start`, `renewal_end`, `escalated_rent`, `notice_due_date`,
  `days_to_notice`, `status`.
- Money values may include `$`, commas, and spaces. Dates are `YYYY-MM-DD`.
  `days_to_notice` is a whole number and may be negative.

## Validation rules

**Whole-file checks** stop the load with a single message:

- The file is not empty.
- The header contains every required column. A missing column is named.

**Row-level checks** do not stop the load. A failing row is left out of the table and
listed in the issues panel with its line number and reason:

- The row has the same number of fields as the header.
- `unit` is present and not a duplicate of an earlier row.
- `tenant` is present.
- `current_rent` and `escalated_rent` parse as money.
- `days_to_notice` is a whole number.
- `lease_end`, `renewal_start`, `renewal_end`, and `notice_due_date` are valid
  `YYYY-MM-DD` dates.
- `status` is present.

## Logic

All money is handled in integer cents and formatted for display with
`Intl.NumberFormat`. Dates are kept as `YYYY-MM-DD` text, which sorts chronologically
as plain text, so a date column sorts correctly without being parsed.

The summary counts the leases in each status: due now, upcoming, and expired.

The table sorts in one of two ways. The default order is by urgency: due now first,
then upcoming, then expired, and within each status by the soonest notice (the
smallest `days_to_notice`). Clicking a column heading sorts by that column ascending;
clicking the same heading again reverses the direction. The sort is stable, so rows
that tie keep their order. Sorting returns a new array and never changes the loaded
data.

## Outputs

- A summary strip: total leases, and counts of due now, upcoming, and expired. The
  due now card switches to the accent tone when the count is above zero.
- A sortable table of leases with current and escalated rent, lease end, the renewal
  term, the notice due date, days to notice, and a status badge. Due now rows are
  tinted and carry a "send notice" flag. The sorted column shows an arrow for the
  direction.
- An issues panel listing every rejected row by line number and reason, hidden when
  there are none.

## Edge cases

- **Escalation match.** Unit 101 shows an escalated rent of `$1,560.00`, the same
  figure the scheduler computed by hand from a `1500.00` rent at 4 percent, proving
  the two tools agree to the cent.
- **Default urgency order.** Among the two due now leases, Unit 103 (notice 72 days
  overdue) sorts ahead of Unit 104 (30 days overdue), because a smaller
  `days_to_notice` is more urgent.
- **Column sort.** Sorting by escalated rent ascending leads with Unit 105 at
  `$1,456.00`; reversing leads with Unit 104 at `$2,080.00`. Sorting by lease end
  leads with the earliest date because dates sort as text.
- **One file, every problem.** `data/messy_renewals.csv` keeps two valid leases in
  the table while the issues panel shows a bad field count, a duplicate unit, and a
  non-numeric `days_to_notice`, all from a single load.
- **Bad header.** `data/invalid_renewals.csv` is missing `status`, so it is refused
  with a message naming the missing column instead of building a half-empty table.
