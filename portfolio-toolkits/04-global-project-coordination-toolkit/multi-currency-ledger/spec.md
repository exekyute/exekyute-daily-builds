# Spec: Multi-Currency Consultant Ledger

## Purpose

Parse a log of consultant invoices submitted in various currencies, convert each one into a single
base currency using an editable exchange-rate dictionary, sum the total consultant spend, and
reconcile that spend against an approved grant total. The run produces a central budget file that the
Burn Rate Tracker reads as its starting figure. This models reconciling incoming consultant invoices
in global currencies against approved grant totals.

## Inputs

- `--invoices`: path to the invoice CSV with an `invoice_id,consultant,currency,amount` header
  (default `data/consultant_invoices.csv`).
- `--grant`: approved grant total in the base currency (default `250000.00`).
- `--out`: path for the central budget file (default `central_budget.json`).

The base currency and the exchange rates live in `rates.py`. The base currency is **USD**. Each rate
is the number of USD that one unit of the foreign currency is worth, so `base = amount * rate`.

## Validation rules

- The invoice file must contain all required columns. A missing column is a clear, immediate error.
- Each invoice id must be non-blank. A blank id row is skipped and counted.
- Each currency code must exist in the exchange-rate dictionary. An unknown code is skipped and
  counted.
- Each amount must be numeric and greater than zero. A blank or non-numeric amount is skipped and
  counted.
- A duplicate invoice id is recorded as a finding. The first occurrence is kept; the repeat does not
  change the running total.

## Logic

1. Load the CSV into row dictionaries and confirm the required columns are present.
2. For each row, validate the id, currency, and amount. A failed row is recorded in `skipped`.
3. Convert the accepted amount to the base currency with `Decimal` math and `ROUND_HALF_UP`,
   quantized to two decimal places.
4. Sum the converted amounts into the total consultant spend.
5. Remaining = grant total minus consultant spend. The run is over budget only when spend is strictly
   greater than the grant total.

## Outputs

- A markdown table printed to the screen: Invoice, Consultant, Currency, Amount, Base (USD).
- A list of skipped and duplicate findings with the reason for each.
- A summary line: accepted / skipped / duplicate counts, consultant spend, grant, and remaining.
- A `central_budget.json` file with `base_currency`, `grant_total`, `consultant_spend`, `remaining`,
  `over_budget`, and `invoice_count`, all monetary values written as fixed-point strings.

## Edge cases

- An unknown currency code (row skipped and counted).
- A blank or non-numeric amount (row skipped and counted).
- A duplicate invoice id (recorded, first kept, not double-counted).
- Spend exactly equal to the grant (treated as within budget, remaining `0.00`).
- Spend one cent over the grant (flagged over budget, remaining negative).

## Sample data design

The included `data/consultant_invoices.csv` is seeded so a single run exercises every path:

- `INV-001` is a clean USD invoice (45,000.00).
- `INV-002` (EUR), `INV-003` (GBP), and `INV-004` (JPY) cover multiple currencies.
- `INV-005` is a second clean USD invoice (15,000.00).
- `INV-006` uses currency `XYZ`, which is not in the rate dictionary (skipped and counted).
- `INV-003` appears a second time (duplicate id; first occurrence kept).
- `INV-007` has a blank amount (skipped and counted).
- `INV-008` has a non-numeric amount (skipped and counted).

The five accepted invoices convert to a consultant spend of **248,600.00 USD**, leaving **1,400.00**
of the 250,000.00 grant. The seeded total sits just under the grant on purpose: adding one more
invoice above 1,400.00 (for example a 2,000.00 USD invoice) would push spend to 250,600.00 and flip
the `over_budget` flag, which is the documented over-budget boundary.

## Hand-off to the Burn Rate Tracker

The `consultant_spend` value of **248,600.00** in `central_budget.json` is the exact figure the Burn
Rate Tracker loads as its starting spend. That shared number is the hand-checked value documented in
the Burn Rate Tracker spec, proving the two tools agree.
