# Spec: Rent Roll and Proration Calculator

## Purpose

Read a CSV of leases and produce an auditable per-unit rent roll for one billing
month. The tool prorates rent for partial-month move-ins and move-outs, applies a
late fee to any overdue balance, totals what each unit owes, and carries the lease
end date through so a reviewer or the companion dashboard can flag upcoming
expirations. Bad rows are reported and skipped so one malformed lease never hides
the rest of the roll.

## Inputs

- A leases CSV. Default `data/sample_leases.csv`, overridable with `--input`.
- Required columns, matched by name in the header (case-insensitive). Extra
  columns are allowed and ignored:
  `unit`, `tenant`, `monthly_rent`, `move_in`, `move_out`, `lease_end`,
  `overdue_balance`.
- The billing month, `--month YYYY-MM` (default `2026-06`).
- The late fee rate on overdue balances, `--late-fee-rate` (default `0.05`, that
  is five percent).
- The output path, `--output` (default `data/sample_rent_roll.csv`).
- `move_in` and `move_out` may be blank. `overdue_balance` blank reads as 0. Money
  values may include `$`, commas, and spaces. Dates must be `YYYY-MM-DD`.

## Validation rules

**Whole-file checks** stop the run with a single message and a non-zero exit code:

- The file exists and is not empty.
- The header contains every required column. A missing column is named.

**Row-level checks** do not stop the run. A failing row is left out of the roll and
reported with its line number and reason:

- The row has the same number of fields as the header (catches a missing field and
  an extra field).
- `unit` is present and is not a duplicate of an earlier row.
- `tenant` is present.
- `monthly_rent` parses as money and is greater than 0.
- `overdue_balance` parses as money and is 0 or greater (blank reads as 0).
- `move_in`, `move_out`, and `lease_end` parse as `YYYY-MM-DD` when present.
- `lease_end` is required.
- When both are present, `move_out` is not before `move_in`.

## Logic

All money math uses `decimal.Decimal` with `ROUND_HALF_UP`, quantized to cents, and
prints fixed-point, never scientific notation. Dates use `datetime` and
`calendar.monthrange`.

For each valid lease, against the billing month from its first to its last day:

- `days_in_month` is the actual day count of the billing month.
- The occupied span runs from `start = max(month_first, move_in or month_first)` to
  `end = min(month_last, move_out or month_last)`.
- `occupied_days = (end - start).days + 1`, inclusive, clamped to 0 when the lease
  is not active in the month (move-out before the month, or move-in after it).
- When `occupied_days` equals `days_in_month`, `prorated_rent = monthly_rent`
  exactly. Otherwise `prorated_rent = monthly_rent * occupied_days / days_in_month`,
  rounded half up to cents.
- `late_fee = overdue_balance * late_fee_rate`, rounded half up to cents, and is 0
  when `overdue_balance` is 0.
- `amount_due = prorated_rent + overdue_balance + late_fee`.

## Outputs

- A console table of every valid unit with monthly rent, occupied days over days in
  the month, prorated rent, overdue balance, late fee, amount due, and lease end.
- A footer with the unit count, the total billed (the sum of amount due), and the
  output path.
- The rent roll CSV with the columns
  `unit, tenant, monthly_rent, billing_month, days_in_month, occupied_days,
  prorated_rent, overdue_balance, late_fee, amount_due, lease_end`, in fixed-point
  money and `YYYY-MM-DD` dates, ready for the dashboard.
- Any skipped rows printed to standard error with line number and reason. The exit
  code is non-zero only when the whole file is rejected.

## Edge cases

- **Full-month lease.** A lease with no move-in or move-out in the month bills the
  full monthly rent, with `occupied_days` equal to `days_in_month`. Unit 102 bills
  `1800.00`.
- **Partial-month move-in (hand-checked).** Unit 101, monthly rent `1500.00`,
  move-in `2026-06-16`, billing June 2026 (30 days): the 16th through the 30th is
  15 days, so prorated rent is `1500.00 * 15 / 30 = 750.00`. This is the figure
  shared with the dashboard spec, proving the two tools agree to the cent.
- **Partial-month move-out.** Unit 103 moves out on `2026-06-10`, billing the 1st
  through the 10th, 10 days, `1650.00 * 10 / 30 = 550.00`.
- **Boundary dates.** Unit 105 moves in on `2026-06-01`, the first of the month, and
  is billed a full month, not a short one. A move-out on the last day is treated the
  same way.
- **Overdue balance and late fee.** Unit 104 carries an overdue balance of `500.00`,
  so a 5 percent late fee of `25.00` is added and the amount due is `2525.00`. Units
  with no overdue balance accrue no fee.
- **Skipped rows.** `sample_leases.csv` repeats unit `101` (duplicate), gives unit
  `107` too few fields, and gives unit `108` an extra field. Each is reported and
  skipped while units 101 to 105 still produce the roll.
- **Whole-file rejection.** `invalid_leases.csv` drops the `lease_end` column, so the
  run stops with `missing required column: lease_end` and exits non-zero instead of
  producing a half-built roll.
