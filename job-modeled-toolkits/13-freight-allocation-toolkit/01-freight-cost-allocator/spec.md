# Spec: Freight Cost Allocator

## Purpose

Allocate one shipment's total freight charge across its line items by an agreed
basis (weight or value), reconcile the rounding remainder so the per-line
allocations sum to the freight total exactly, and write an auditable per-line
landed-cost CSV. The output feeds the Shipment Landed-Cost Dashboard (the second
tool in this repo).

## Inputs

- A shipment line-items CSV. Default file: `data/sample_shipment.csv`. Columns:

  | Column        | Meaning                                  |
  |---------------|------------------------------------------|
  | `line_id`     | Unique identifier for the line           |
  | `description` | Free text label                          |
  | `quantity`    | Whole number of units, greater than 0    |
  | `unit_cost`   | Dollars per unit, 0 or greater           |
  | `weight`      | Total line weight in lbs, 0 or greater   |

  Line **value** (used by the value basis) is computed as `quantity * unit_cost`.
  It is not stored in the CSV, so it can never drift from quantity and unit cost.
  The two bases are therefore **weight** (the `weight` column) and **value**
  (extended `quantity * unit_cost`).

- Command-line options:
  - `--freight` total freight charge in dollars (default `100.00`).
  - `--basis` `weight` or `value` (default `value`).
  - `--input` line-items CSV (default `data/sample_shipment.csv`).
  - `--output` landed-cost CSV path (default `out/landed_cost.csv`).

## Validation rules

The run aborts and lists every problem at once, each tagged with the line number
it came from, if any of these fail:

- The input file exists and is readable.
- The header contains all required columns (missing columns are named).
- The file has at least one data row.
- `line_id` is present on every row and unique across the file.
- `quantity` parses as a whole number greater than 0.
- `unit_cost` parses as a number 0 or greater.
- `weight` parses as a number 0 or greater.
- No row carries more fields than the header.
- `--freight` parses as a number 0 or greater.
- The chosen basis has a positive total across all lines. A single zero line is
  allowed; an all-zero basis total (every weight 0, or every value 0) is rejected
  because freight cannot be shared out across nothing.

## Logic

All money math uses `decimal.Decimal` with `ROUND_HALF_UP`. The allocation runs
in integer cents so the reconciliation is exact.

1. Convert the freight charge to integer cents: `freight_cents`.
2. For each line, take its basis amount `b_i`: the `weight` column (weight basis)
   or `quantity * unit_cost` (value basis). Let `total` be the sum of all `b_i`.
3. Compute the exact share `exact_i = freight_cents * b_i / total`.
4. Split each share into a floor part `floor_i` and a fractional `remainder_i`.
5. The cents lost to flooring are `leftover = freight_cents - sum(floor_i)`.
6. Hand those `leftover` cents out one at a time to the lines with the largest
   `remainder_i`, breaking ties by input order so the result is deterministic.
7. Each line's allocation is `floor_i` plus 1 if it won a leftover cent. By
   construction the allocations sum to `freight_cents` exactly.

Because the remainders sum to the (whole-number) leftover and each remainder is
below 1, there are always strictly more positive-remainder lines than there are
leftover cents. A zero-weight or zero-value line therefore never receives a cent.

`landed_unit_cost` is `unit_cost + allocated_freight / quantity`, rounded to the
cent for display. Exact reconciliation is done on the allocated freight and the
line value, not on this rounded per-unit figure.

## Outputs

- A console table: line_id, description, quantity, unit_cost, basis amount,
  allocated freight, landed unit cost. All money prints fixed-point to the cent
  (for example `33.34`), never scientific notation. A summary line shows the
  freight entered, the total allocated, and whether they match.
- A landed-cost CSV with columns `line_id`, `description`, `quantity`,
  `unit_cost`, `allocated_freight`, `landed_unit_cost`. Money is stored as
  fixed two-place strings. The dashboard derives total freight as the sum of
  `allocated_freight` and total landed cost as the sum of
  `quantity * unit_cost + allocated_freight`, straight from these columns.

A curated copy of one clean run is committed at `data/landed_cost.csv` (the
`--freight 100.00 --basis value` run described below). The dashboard loads that
file as its sample.

## Hand-checked example

This is the exact example that ties the two tools together. Command:

    python cli.py --freight 100.00 --basis value --output data/landed_cost.csv

Input lines and their value (`quantity * unit_cost`):

| line_id | quantity | unit_cost | value  | weight |
|---------|----------|-----------|--------|--------|
| L001    | 7        | 5.00      | 35.00  | 20.0   |
| L002    | 3        | 10.00     | 30.00  | 12.0   |
| L003    | 5        | 4.00      | 20.00  | 0.0    |
| L004    | 2        | 0.00      | 0.00   | 8.0    |
| L005    | 1        | 50.00     | 50.00  | 60.0   |

Total value is 135.00. Allocating 10000 cents by value gives exact shares of
2592.59, 2222.22, 1481.48, 0.00, and 3703.70 cents. The floors sum to 9998, so
2 cents are left over. The two largest remainders are L005 (.70) and L001 (.59),
so each gains one cent:

| line_id | allocated_freight | landed_unit_cost |
|---------|-------------------|------------------|
| L001    | 25.93             | 8.70             |
| L002    | 22.22             | 17.41            |
| L003    | 14.81             | 6.96             |
| L004    | 0.00              | 0.00             |
| L005    | 37.04             | 87.04            |

The allocated freight sums to **100.00**, matching the charge exactly. Total
landed cost is total goods value (135.00) plus total freight (100.00) = **235.00**.
The dashboard reads this same CSV and reports the identical totals.

## Edge cases (exercised by the sample data)

- **Clean even split.** Running the sample by `weight` divides 100.00 into
  20.00 / 12.00 / 0.00 / 8.00 / 60.00 with no remainder.
- **Uneven split needing reconciliation.** Running the sample by `value` (above)
  leaves 2 cents that the largest-remainder step distributes.
- **Zero-basis line under each basis.** L003 has zero weight (gets 0 under the
  weight basis); L004 has zero value (gets 0 under the value basis).
- **Boundary value.** L005 dominates both bases and takes the largest share.
- **Bad data.** `data/invalid_shipment.csv` holds a missing quantity, a
  non-numeric quantity, a zero quantity, a duplicate `line_id`, and a row with an
  extra field. A run against it is rejected with one message per problem.
