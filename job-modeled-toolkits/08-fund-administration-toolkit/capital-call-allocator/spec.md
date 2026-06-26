# Capital Call Allocator, specification

## Purpose

Split a fund's total capital call across its investors in proportion to each
investor's commitment, reconcile the rounding so the per-investor amounts add up
to the call total to the penny, and write a per-investor allocation CSV that the
Investor Allocation Dashboard can load.

## Inputs

- `--call-total`: the total capital call in dollars, for example `250000.00`.
- `--commitments`: path to a CSV with the header `investor,commitment` and one
  row per investor. Commitment is a dollar figure.
- `--output`: path where the allocation CSV is written.

Example commitments file:

```
investor,commitment
Aurora Capital,4000000
Brightwater LP,3500000
Cedar Grove Partners,2500000
Dunes Family Office,1000000
Echo Ventures,0
```

## Validation rules

Every problem is reported in one pass; nothing is written when any check fails.

- The commitments file must not be empty and must contain at least one investor row.
- The header must be exactly `investor,commitment`.
- Each row must have exactly two fields. A row with one field (missing) or three
  fields (extra) is rejected with its line number.
- The investor name must not be blank.
- The commitment must be a valid number and must not be negative.
- Investor names must be unique. A repeat names the line it first appeared on.
- The total commitment across all investors must be greater than zero.
- The call total must be a valid number greater than zero.

## Logic

1. Convert the call total to whole cents using `ROUND_HALF_UP`.
2. For each investor, compute the exact share of those cents as
   `call_cents * commitment / total_commitment`, kept as an exact `Decimal`.
3. Round each share to whole cents with `ROUND_HALF_UP` and record the dropped
   fraction.
4. Compare the sum of the rounded shares with the call total. Distribute any
   difference one cent at a time with the largest-remainder method: extra cents
   go to the largest dropped fractions, and any over-rounding is taken back from
   the smallest. Ties are broken by larger commitment, then by name order, so the
   result is the same every run.
5. Convert the reconciled cents back to two-decimal dollars.

Ownership percentage is `commitment / total_commitment * 100`, rounded to four
decimal places for display.

## Outputs

A CSV with the header `investor,commitment,ownership_pct,called_amount`, one row
per investor in input order. All dollar values are written as fixed-point numbers
with two decimals (never scientific notation). The called amounts sum to the call
total exactly.

## Edge cases

- A zero-commitment investor receives a zero called amount and zero ownership,
  and is still listed.
- When shares round to one cent short of (or over) the call, the largest-remainder
  step reconciles the difference, so no penny is ever lost or gained.
- Files with missing fields, extra fields, duplicate investors, blank names,
  non-numeric or negative commitments, or an all-zero total are rejected with a
  full list of issues and produce no output.

## Hand-checked example

This is the example shipped in `sample_data/` and the figure the dashboard is
checked against.

Call total: `250000.00`. Commitments:

| Investor              | Commitment | Ownership | Exact cents        | Rounded   |
| --------------------- | ---------- | --------- | ------------------ | --------- |
| Aurora Capital        | 4,000,000  | 36.3636%  | 9,090,909.0909     | 90,909.09 |
| Brightwater LP        | 3,500,000  | 31.8182%  | 7,954,545.4545     | 79,545.45 |
| Cedar Grove Partners  | 2,500,000  | 22.7273%  | 5,681,818.1818     | 56,818.18 |
| Dunes Family Office   | 1,000,000  |  9.0909%  | 2,272,727.2727     | 22,727.27 |
| Echo Ventures         | 0          |  0.0000%  | 0                  |      0.00 |

The rounded amounts sum to `249,999.99`, one cent short of the call. The largest
dropped fraction belongs to Brightwater LP (`.4545`), so it receives the single
reconciling cent and becomes `79,545.46`. The final called amounts sum to
`250,000.00` exactly. Loaded into the dashboard, these rows produce the same
per-investor figures and the same total.
