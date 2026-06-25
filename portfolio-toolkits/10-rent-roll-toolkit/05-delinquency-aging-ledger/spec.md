# Spec: Delinquency and Aging Ledger

## Purpose

Read a CSV of charges and payments and produce a delinquency report for one reference
date. For each unit the tool computes the open balance, ages it by the number of days
past its due date, applies a late fee once the grace period has passed, and totals
what is owed. Charges that are fully paid are left off the report as settled. Bad rows
are reported and skipped. The output CSV feeds the companion delinquency dashboard.

## Inputs

- A charges ledger CSV. Default `data/sample_ledger.csv`, overridable with `--input`.
- Required columns, matched by name in the header (case-insensitive). Extra columns
  are allowed and ignored: `unit`, `tenant`, `charge_type`, `due_date`,
  `amount_charged`, `amount_paid`.
- The reference date, `--as-of YYYY-MM-DD` (default `2026-06-12`).
- The grace period, `--grace-days` (default `5`).
- The late fee rate, `--late-fee-rate` (default `0.05`, that is five percent).
- The output path, `--output` (default `data/aging.csv`).
- Money values may include `$`, commas, and spaces. `due_date` must be `YYYY-MM-DD`.

## Validation rules

**Whole-file checks** stop the run with a single message and a non-zero exit code:

- The file exists and is not empty.
- The header contains every required column. A missing column is named.

**Row-level checks** do not stop the run. A failing row is left out and reported with
its line number and reason:

- The row has the same number of fields as the header.
- `unit` is present and is not a duplicate of an earlier row.
- `tenant` and `charge_type` are present.
- `amount_charged` parses as money and is greater than 0.
- `amount_paid` parses as money and is 0 or greater.
- `due_date` parses as `YYYY-MM-DD` and is present.

## Logic

All money math uses `decimal.Decimal` with `ROUND_HALF_UP`, quantized to cents.

For each valid charge, against the reference date:

- `balance = amount_charged - amount_paid`. A charge with a balance of 0 or less is
  settled and left off the report (counted in the footer).
- `days_overdue = as_of - due_date` in whole days, never negative. A charge not yet
  due reads as 0.
- The aging `bucket` is `current` at 0 days, then `1-30`, `31-60`, `61-90`, and `90+`.
  Aging is by the actual days past due, so the grace period does not move a charge
  between buckets.
- `late_fee = balance * late_fee_rate`, rounded half up, but only once `days_overdue`
  is past the grace period. A charge inside the grace window carries no fee yet.
- `total_owed = balance + late_fee`.

## Outputs

- A console table of every delinquent charge with its balance, days overdue, bucket,
  late fee, and total owed.
- A bucket summary: the count and total owed in each of the five buckets, in aging
  order.
- A footer with the delinquent charge count, the total owed, and how many charges were
  settled and left off.
- The aging CSV with the columns
  `unit, tenant, charge_type, due_date, balance, days_overdue, bucket, late_fee,
  total_owed`, in fixed-point money and `YYYY-MM-DD` dates, ready for the dashboard.
- Any skipped rows printed to standard error. The exit code is non-zero only when the
  whole file is rejected.

## Edge cases

- **All five buckets.** The sample fills every bucket: Unit 101 is `current` (not yet
  due), Units 102, 103, and 105 are `1-30`, Unit 104 is `31-60`, Unit 106 is `61-90`,
  and Unit 107 is `90+`.
- **Bucket boundary.** Unit 103 at exactly 30 days overdue lands in `1-30`, while Unit
  104 at 31 days lands in `31-60`.
- **Grace period.** Unit 102 is 3 days past due, inside the 5-day grace window, so it
  ages into `1-30` but carries a late fee of `0.00`. Past the window, Unit 104 accrues
  a `100.00` fee on its `2000.00` balance.
- **Settled charges left off.** Unit 108 is paid in full (balance 0) and Unit 109 is
  overpaid (balance below 0); both are settled and left off the report, counted in the
  footer.
- **Skipped rows.** The sample repeats unit `101`, gives one row too few fields and
  one too many, and includes a non-numeric amount and a bad date; each is reported and
  skipped.
- **Whole-file rejection.** `invalid_ledger.csv` drops the `due_date` column, so the
  run stops with `missing required column: due_date` and exits non-zero.
