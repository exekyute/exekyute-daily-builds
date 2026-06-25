# Amortization Schedule Generator, specification

## Purpose

Take a loan principal, an annual interest rate, and a term in months; compute the
level monthly payment; build a full amortization schedule that splits each
payment into interest and principal with a running balance; reconcile the final
period so the balance closes at exactly zero; and write the schedule to a CSV the
Loan Balance Dashboard can load. All money math uses `decimal.Decimal` with
`ROUND_HALF_UP` and is written as fixed-point with two decimals, never scientific
notation.

## Inputs

Command-line flags:

- `--principal`: the loan amount in dollars, for example `1000.00`.
- `--annual-rate`: the annual interest rate as a percent, for example `12` or
  `12.5`.
- `--term-months`: the number of monthly payments, a whole number, for example
  `6`.
- `--output`: the path where the schedule CSV is written.

Example:

```
python amortize.py --principal 1000.00 --annual-rate 12 --term-months 6 --output sample_data/schedule.csv
```

## Validation rules

Every problem is reported in one pass; nothing is written when any check fails.

- The principal must be a valid number and strictly greater than zero.
- The annual rate must be a valid number and must not be negative. Zero is
  allowed, because an interest-free loan is valid.
- The term must parse as a whole integer and must be at least 1. A fractional
  term such as `6.5` or a term of `0` or less is rejected.
- The output path must be provided and writable.

## Logic

1. Convert the principal to a two-decimal cent value with `ROUND_HALF_UP` and
   derive the monthly rate as `annual_rate / 100 / 12`, kept as an exact
   `Decimal` multiplier.
2. Compute the level payment. For a zero-rate loan it is `principal / term`.
   Otherwise it is the standard amortization formula
   `principal * r / (1 - (1 + r) ** -term)`. Round the payment to cents.
3. For each period, compute `interest = round(balance * r)`, then
   `principal_paid = payment - interest`, then `balance = balance - principal_paid`,
   each rounded to cents.
4. Reconcile the final period: set its principal to whatever balance remains and
   its payment to interest plus that principal, so the closing balance is exactly
   `0.00` with no residual cent.
5. Accumulate total interest and total of payments across the schedule.

## Outputs

A CSV with the header `period,payment,interest,principal,balance`, one row per
period in order. All dollar values are fixed-point with two decimals. The final
`balance` is `0.00`. The tool also prints a short run summary to the terminal:
the level payment, total interest, total of payments, and final balance.

## Edge cases

- Zero-interest loan: every period shows `0.00` interest, the principal equals
  the level payment, and the final period still reconciles any cent of rounding
  drift so the balance closes at zero.
- Single-period loan (`--term-months 1`): one row whose payment is the principal
  plus one month of interest, closing at zero.
- Final-period rounding: in the shipped six-period example the regular `172.55`
  would overpay, so the last payment drops to `172.53` and no penny is lost or
  gained.
- Boundary values: a term of `1` and a rate of `0` are accepted. A principal of
  `0`, a negative rate, a term of `0`, a fractional term, or any non-numeric
  input is rejected with a full list of issues and produces no output file.

## Hand-checked example

This is the loan shipped in `sample_data/schedule.csv` and the figure the
dashboard is checked against.

Principal `1000.00`, annual rate `12%` (1.00% per month), term `6` months. The
level payment is `1000 * 0.01 / (1 - 1.01 ** -6) = 172.5484...`, which rounds to
`172.55`.

| Period | Opening balance | Interest | Principal | Payment | Closing balance |
| ------ | --------------- | -------- | --------- | ------- | --------------- |
| 1 | 1000.00 | 10.00 | 162.55 | 172.55 | 837.45 |
| 2 |  837.45 |  8.37 | 164.18 | 172.55 | 673.27 |
| 3 |  673.27 |  6.73 | 165.82 | 172.55 | 507.45 |
| 4 |  507.45 |  5.07 | 167.48 | 172.55 | 339.97 |
| 5 |  339.97 |  3.40 | 169.15 | 172.55 | 170.82 |
| 6 |  170.82 |  1.71 | 170.82 | 172.53 | 0.00 |

The total interest paid is `35.28` and the total of payments is `1035.28`, which
equals the principal of `1000.00` plus the `35.28` of interest. Loaded into the
dashboard, these rows produce the same per-period figures, the same totals, and a
final balance of `0.00`.
