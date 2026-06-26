# Spec: Security Deposit Reconciliation

## Purpose

Read a CSV of move-outs and reconcile each tenant's security deposit against the
itemized deductions taken from it. For each move-out the tool totals the deductions,
subtracts them from the deposit held, and reports either a refund owed to the tenant, a
balance the tenant still owes, or an even result. Bad rows are reported and skipped.
The output CSV feeds the companion deposit settlement dashboard.

## Inputs

- A move-outs CSV. Default `data/sample_moveouts.csv`, overridable with `--input`.
- Required columns, matched by name in the header (case-insensitive). Extra columns
  are allowed and ignored: `unit`, `tenant`, `move_out_date`, `deposit_held`,
  `unpaid_rent`, `cleaning`, `damages`.
- The output path, `--output` (default `data/deposit_recon.csv`).
- The deduction columns (`unpaid_rent`, `cleaning`, `damages`) may be blank, which
  reads as 0. Money values may include `$`, commas, and spaces. `move_out_date` must
  be `YYYY-MM-DD`.

## Validation rules

**Whole-file checks** stop the run with a single message and a non-zero exit code:

- The file exists and is not empty.
- The header contains every required column. A missing column is named.

**Row-level checks** do not stop the run. A failing row is left out and reported with
its line number and reason:

- The row has the same number of fields as the header.
- `unit` is present and is not a duplicate of an earlier row.
- `tenant` is present.
- `deposit_held` parses as money and is 0 or greater.
- `unpaid_rent`, `cleaning`, and `damages` each parse as money and are 0 or greater
  (blank reads as 0).
- `move_out_date` parses as `YYYY-MM-DD` and is present.

## Logic

All money math uses `decimal.Decimal` with `ROUND_HALF_UP`, quantized to cents.

For each valid move-out:

- `total_deductions = unpaid_rent + cleaning + damages`.
- `net = deposit_held - total_deductions`.
- When `net` is positive, `refund_due = net`, `balance_owed = 0`, and the result is
  `refund`.
- When `net` is negative, `refund_due = 0`, `balance_owed = -net`, and the result is
  `balance`.
- When `net` is exactly 0, both are 0 and the result is `even`.

## Outputs

- A console table of every move-out with the deposit held, total deductions, refund
  due, balance owed, and result.
- A footer with the move-out count, the number and total of refunds, the number and
  total of balances owed, and the number of even results.
- The reconciliation CSV with the columns
  `unit, tenant, move_out_date, deposit_held, unpaid_rent, cleaning, damages,
  total_deductions, refund_due, balance_owed, result`, in fixed-point money and
  `YYYY-MM-DD` dates, ready for the dashboard.
- Any skipped rows printed to standard error. The exit code is non-zero only when the
  whole file is rejected.

## Edge cases

- **Full refund.** Unit 101 has no deductions, so its `1500.00` deposit is refunded in
  full.
- **Partial refund.** Unit 102 has `400.00` of deductions against an `1800.00` deposit,
  leaving a `1400.00` refund.
- **Even result.** Unit 103 has `1650.00` of unpaid rent against a `1650.00` deposit, so
  the net is exactly 0 and there is neither a refund nor a balance.
- **Balance owed.** Unit 104 has `2300.00` of deductions against a `2000.00` deposit, so
  the tenant owes `300.00`.
- **Blank deductions.** Unit 105 leaves its deduction columns blank, which read as 0, so
  its `1400.00` deposit is refunded in full.
- **Skipped rows.** The sample repeats unit `101`, gives one row too few fields and one
  too many, and includes a non-numeric deposit and a bad date; each is reported and
  skipped.
- **Whole-file rejection.** `invalid_moveouts.csv` drops the `deposit_held` column, so
  the run stops with `missing required column: deposit_held` and exits non-zero.
