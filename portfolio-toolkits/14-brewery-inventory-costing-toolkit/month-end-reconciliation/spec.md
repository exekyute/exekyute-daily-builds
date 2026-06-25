# Month-End Reconciliation

## Purpose
Loads the costing engine's perpetual valuation and excise summary alongside the
warehouse physical count, reconciles book to count for every SKU, flags variances
over tolerance, and rolls up closing inventory value and excise duty for month-end.
A junior inventory accountant runs it after the count sheet comes in.

## Inputs
Three CSVs, loaded into SQLite:

`perpetual_valuation.csv` (from the costing engine): `sku`, `description`,
`category`, `on_hand_qty`, `stock_unit`, `wac_unit_cost`, `inventory_value`,
`integrity_flag`.

`excise_summary.csv` (from the costing engine): `abv_class`, `hectolitres`,
`excise_duty`.

`physical_counts.csv` (entered by the warehouse): `sku`, `counted_qty`.

## Validation rules
The reconciliation view is built so data problems surface instead of being
dropped by the join:

- A SKU in the perpetual records with no matching count is reported as `not counted`.
- A SKU in the count with no perpetual record is reported as `no perpetual record`.
- A SKU whose value variance exceeds the $20.00 tolerance is reported as `over tolerance`.
- Everything else is `ok`.

## Logic
1. `schema.sql` creates the three tables and a `reconciliation` view. The view
   full-joins perpetual to count (emulated with two left joins) so a SKU on
   either side appears once.
2. Quantity variance is `counted_qty - on_hand_qty`. Value variance is that
   quantity variance priced at the SKU's weighted-average unit cost, rounded to
   the cent. The status comes from the tolerance test above.
3. `queries.sql` holds the named queries: the full reconciliation, the exceptions
   only, closing value by category, total closing value, excise by ABV class, and
   total excise. Rounding matches the costing engine so the totals agree.
4. `run.py` loads the CSVs, runs each query, prints the results, and asserts the
   totals against the hand-checked figures below, printing PASS or FAIL.

## Outputs
Printed tables for each query, then a PASS or FAIL line. Nothing is written to disk.

## Edge cases
The sample inputs are built to exercise each branch:

- **Clean match** with zero variance (FG-LAGER-CAN, PKG-CAN-355).
- **Small variance within tolerance** that stays `ok` (RM-MALT-2ROW, value variance -$10.35).
- **Variance over tolerance** that is flagged (RM-HOPS-CASCADE, FG-KEG-IPA).
- **A flagged SKU carrying a negative perpetual balance** (PKG-LABEL-IPA).
- **A SKU counted but not on the books** (FG-STOUT-CAN, `no perpetual record`).
- **A SKU on the books but not counted** (FG-RADLER-CAN, `not counted`).

### Hand-checked example
RM-HOPS-CASCADE closes at 50 kg on the books at a weighted-average $15.0334 per
kg. The count finds 45 kg. Quantity variance is -5 kg; value variance is
-5 times $15.0334 = -$75.17, which clears the $20.00 tolerance and is flagged.

Across the file the totals are: closing inventory value **$25,448.34** (finished
goods $21,540.00, raw materials $1,398.34, packaging $2,510.00), **five** SKUs on
the exception list, and total excise duty **$423.34**. These are the same figures
the costing engine produced and `test_costing.py` checked, so the two tools agree
to the cent. `run.py` asserts all of them.
