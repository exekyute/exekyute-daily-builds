# Inventory Costing Engine

## Purpose
Replays a brewery's raw material, packaging, and finished goods transactions for
a period, keeps a perpetual weighted-average cost for every SKU, and computes the
federal excise duty on the beer packaged in that period. A junior inventory
accountant runs it at month-end to produce the valuation and the duty figure.

## Inputs
One transaction CSV, one row per inventory movement, with these columns:

| Column | Type | Notes |
| --- | --- | --- |
| txn_id | text | Unique across the file. |
| date | text | ISO date, recorded but not used in the math. |
| sku | text | Stock-keeping unit the row affects. |
| description | text | Plain name carried through to the output. |
| category | text | `raw_material`, `packaging_material`, or `finished_goods`. |
| txn_type | text | `opening`, `receipt`, `package`, or `issue`. |
| quantity | number | Greater than zero, in the SKU's stock unit. |
| unit | text | Stock unit: `kg`, `each`, `case`, `keg`, `L`, `hL`, and so on. |
| unit_price | number | Purchase price per unit on receipts; the standard cost per unit on a finished goods package. |
| freight | number | Total freight on a receipt line. Blank or zero otherwise. |
| customs_duty | number | Total import duty on a receipt line, for example on imported hops. Blank or zero otherwise. |
| abv_class | text | On `package` rows only: `over_2_5`, `over_1_2_to_2_5`, or `not_over_1_2`. |
| litres_per_unit | number | On `package` rows only: litres of beer per stock unit, used to convert cases and kegs to hectolitres. |

A second figure, `--ytd-hl`, is the total beer of every ABV class already brewed
this calendar year before this file. It sets where the period's volume falls in
the reduced-rate excise brackets.

## Validation rules
The file is rejected, with no output written, if any row fails a check. Each
failure names the row and the problem:

- A required column is missing from the header.
- `txn_id` is blank or repeats an earlier `txn_id`.
- `sku` or `unit` is blank.
- `category` is not one of the three allowed values.
- `txn_type` is not one of the four allowed values.
- `quantity` is not a number, or is zero or negative.
- `unit_price`, `freight`, `customs_duty`, or `litres_per_unit` is non-numeric or negative.
- An `opening`, `receipt`, or `package` row has no `unit_price`.
- An `opening` row carries freight or customs duty (an opening balance is a starting position, not a purchase).
- A `package` row is missing `abv_class` or `litres_per_unit`, or `litres_per_unit` is not positive.
- `abv_class` appears on a row that is not a `package`.

## Logic
1. Group the rows by SKU in the order each SKU first appears.
2. Replay each SKU's transactions in file order:
   - `opening`, `receipt`, and `package` add to the balance. The amount added is the landed cost: quantity times unit price, plus freight, plus customs duty.
   - The new weighted-average value is the running value plus the landed cost; the new unit cost is value divided by quantity.
   - `issue` draws the balance down at the current weighted-average unit cost.
   - If on-hand quantity ever goes below zero, the SKU is marked with a `negative on-hand` integrity flag, and processing continues so the bad data is visible.
3. For each `package` row, convert the quantity to litres (cases and kegs through `litres_per_unit`, volume units through a fixed factor) and then to hectolitres at 100 litres each. Thread a single cumulative production figure, starting at `--ytd-hl`, through the package rows in file order. Split each row's volume across the reduced-rate brackets it spans, applying that beer's ABV-class rate in each bracket, and the regular rate on any volume past the 75,000 hL annual limit. Total the duty by ABV class.

Money is held as `decimal.Decimal` and rounded half up to the cent. Weighted-average
unit cost is shown to four decimal places. The excise rates are the CRA rates per
hectolitre effective April 1, 2026, written out in `costing.py`.

## Outputs
Two CSVs, written to `--out-dir`:

`perpetual_valuation.csv`: one row per SKU with `sku`, `description`, `category`,
`on_hand_qty`, `stock_unit`, `wac_unit_cost`, `inventory_value`, `integrity_flag`.

`excise_summary.csv`: one row per ABV class with `abv_class`, `hectolitres`,
`excise_duty`.

## Edge cases
The sample data is built to exercise each branch:

- **Clean weighted average** with freight folded in (RM-MALT-2ROW).
- **Imported receipt** carrying customs duty in the landed cost (RM-HOPS-CASCADE).
- **Even issue** that divides without rounding (PKG-CAN-355).
- **Negative on-hand** from an over-issue, which sets the integrity flag (PKG-LABEL-IPA).
- **Excise across a bracket boundary**, where the period's strong beer crosses the 2,000 hL line.
- A separate `sample_transactions_invalid.csv` carries a duplicate id, a negative quantity, a non-numeric price, a bad category, a misplaced `abv_class`, and a package missing its excise fields, so the rejection path can be seen.

### Hand-checked example
RM-MALT-2ROW (kilograms):

- Opening 1,000 kg at $1.20 = $1,200.00 value.
- Receipt 2,000 kg at $1.25 ($2,500.00) plus $180.00 freight = $2,680.00 landed. Balance 3,000 kg, $3,880.00, unit cost $1.293333.
- Issue 2,500 kg at $1.293333 = $3,233.33. Ending balance 500 kg, $646.67, unit cost $1.2933.

Excise on the period's strong beer (over 2.5% ABV), starting from 1,960.00 hL
already brewed this year:

- Lager and IPA package to 71.90 hL, taking cumulative production from 1,960.00 to 2,031.90 hL.
- 40.00 hL falls in the first bracket at $3.769 = $150.76.
- 31.90 hL falls in the second bracket at $7.538 = $240.4622.
- Strong-beer duty = $391.22.

The radler (8.52 hL, over 1.2% to 2.5%) sits in the second bracket at $3.770 =
$32.12. Total excise = **$423.34**. Total inventory value across all seven SKUs
= **$25,448.34**. Both figures are checked by `test_costing.py` here and again by
the reconciliation runner in the other tool.
