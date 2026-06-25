# Spec: Lease Renewal and Escalation Scheduler

## Purpose

Read a CSV of leases and produce a renewal schedule for one reference date. For each
lease the tool works out the next term's start and end, the escalated rent for that
term, and the date a renewal notice is due, then classifies the lease as due now,
upcoming, or expired. Bad rows are reported and skipped so one malformed lease never
hides the rest of the schedule. The output CSV feeds the companion renewal tracker.

## Inputs

- A leases CSV. Default `data/sample_leases.csv`, overridable with `--input`. This is
  the same leases file the rent roll calculator reads; only four of its columns are
  needed here and any others are ignored.
- Required columns, matched by name in the header (case-insensitive): `unit`,
  `tenant`, `monthly_rent`, `lease_end`.
- The reference date, `--as-of YYYY-MM-DD` (default `2026-06-12`).
- The notice lead time, `--notice-days` (default `90`).
- The rent increase for the next term, `--escalation-rate` (default `0.04`, that is
  four percent).
- The renewed term length, `--term-months` (default `12`).
- The output path, `--output` (default `data/renewals.csv`).
- Money values may include `$`, commas, and spaces. `lease_end` must be `YYYY-MM-DD`.

## Validation rules

**Whole-file checks** stop the run with a single message and a non-zero exit code:

- The file exists and is not empty.
- The header contains every required column. A missing column is named.

**Row-level checks** do not stop the run. A failing row is left out of the schedule
and reported with its line number and reason:

- The row has the same number of fields as the header.
- `unit` is present and is not a duplicate of an earlier row.
- `tenant` is present.
- `monthly_rent` parses as money and is greater than 0.
- `lease_end` parses as `YYYY-MM-DD` and is present.

## Logic

All money math uses `decimal.Decimal` with `ROUND_HALF_UP`, quantized to cents. Dates
use `datetime` and `calendar`.

For each valid lease, against the reference date:

- `renewal_start = lease_end + 1 day`.
- `renewal_end` is `renewal_start` advanced by `term_months` months, minus one day.
  Advancing months clamps to the last valid day of the target month, so the end of a
  long month never rolls into the next one.
- `escalated_rent = monthly_rent * (1 + escalation_rate)`, rounded half up to cents.
- `notice_due_date = lease_end - notice_days`.
- `days_to_notice = notice_due_date - as_of` in whole days, negative once the notice
  date has passed.
- `status` is `expired` when `lease_end` is before the reference date, `due_now` when
  the lease is still active but the reference date is on or after the notice date, and
  `upcoming` otherwise.

## Outputs

- A console table of every valid unit with current rent, escalated rent, lease end,
  renewal start and end, notice due date, days to notice, and status.
- A footer with the lease count and how many are due now, upcoming, and expired.
- The renewals CSV with the columns
  `unit, tenant, current_rent, lease_end, renewal_start, renewal_end, escalated_rent,
  notice_due_date, days_to_notice, status`, in fixed-point money and `YYYY-MM-DD`
  dates, ready for the tracker.
- Any skipped rows printed to standard error with line number and reason. The exit
  code is non-zero only when the whole file is rejected.

## Edge cases

- **Escalation (hand-checked).** Unit 101 at `1500.00` with the default 4 percent rate
  escalates to `1500.00 * 1.04 = 1560.00`. This is the figure shared with the tracker
  spec, proving the two tools agree to the cent.
- **Month-end clamp.** Advancing months clamps the day to the target month, so a term
  that lands on a short month ends on its last valid day rather than spilling over. A
  lease ending `2026-01-31` would renew through the clamped end of the term month.
- **Due now.** Units 103 and 104 are still active but already inside the 90-day notice
  window as of `2026-06-12`, so they read as `due_now` with a negative days to notice.
- **Upcoming.** Units 101, 102, and 105 end far enough out that their notice dates are
  still in the future, so they read as `upcoming`.
- **Expired.** Unit 109 ended `2026-05-31`, before the reference date, so it reads as
  `expired`.
- **Notice boundary.** When the reference date equals the notice date exactly, the
  notice is due now, not upcoming.
- **Skipped rows.** `sample_leases.csv` repeats unit `101`, gives unit `107` too few
  fields, and gives unit `108` an extra field; each is reported and skipped.
- **Whole-file rejection.** `invalid_leases.csv` drops the `lease_end` column, so the
  run stops with `missing required column: lease_end` and exits non-zero.
