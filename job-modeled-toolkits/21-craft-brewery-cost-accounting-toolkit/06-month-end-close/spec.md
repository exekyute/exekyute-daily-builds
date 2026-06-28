# Month-End Close

## Purpose
Reconciles the book inventory against the warehouse physical count, flags the
variances that are worth a person's attention, generates the closing journal
entries, and proves the books balance. A cost accountant runs it at the end of
the period to close inventory and post the cost entries. It is the tool that ties
the pipeline together: its valuation total matches the perpetual valuation tool,
and its excise total matches the excise duty engine, to the cent.

## Inputs
Four CSVs from the upstream tools, loaded into SQLite:

- `perpetual_valuation.csv` (from the valuation tool): book inventory by SKU.
- `physical_counts.csv`: the counted quantity per SKU. Columns `sku`, `counted_qty`.
- `sku_margins.csv` (from the margin tool): revenue and cost of goods by sales line.
- `excise_summary.csv` (from the excise tool): duty by ABV class.

## Validation rules
The reconciliation joins the physical count to the book inventory by SKU. A SKU
present in one and not the other simply does not appear in the join, which is
itself visible in the output. The tolerance for a count variance is **$50.00 of
value**. A variance past that, or any SKU carrying an integrity flag, is an
exception.

## Logic
The queries, in `queries.sql`, each answer one plain question:

1. **valuation_total** and **valuation_by_category**: the book inventory value, in total and by category.
2. **reconciliation**: for each SKU, the book quantity, the counted quantity, the quantity variance, the value of that variance at the weighted-average unit cost, and whether it is within or over the $50.00 tolerance.
3. **exceptions**: count variances over tolerance, plus SKUs carrying an integrity flag such as a negative on-hand balance.
4. **excise_total**: the total federal excise duty.
5. **journal_entries**: the closing entries built from the period's data, sales, cost of goods sold, excise duty, and the adjustment that writes book inventory to the physical count, each with equal debits and credits.
6. **trial_balance**: total debits and total credits, summed separately. A balanced close has the two equal.

Money is stored as `REAL` and every monetary total is wrapped in `ROUND(x, 2)`;
the runner re-checks each total with `decimal.Decimal`, so the figures agree with
the Python engines to the cent. The runner is the test: it asserts the totals
against the figures below and prints PASS or FAIL.

## Outputs
The runner prints each query result as a table, then a PASS or FAIL line. There
is no output file; the close is a report.

## Edge cases
The sample data exercises each branch:

- **A clean SKU** with no variance (PKG-CAN-355).
- **A small variance within tolerance** (RM-MALT, 15 kg short, $18.94).
- **A variance over tolerance** (RM-HOPS, 8 kg short, $157.44), flagged as an exception.
- **An overage** rather than a shortage (FG-RADLER-CAN, 20 cans over).
- **An integrity flag** carried from the valuation tool (RM-FININGS, negative on-hand), listed as an exception regardless of its count.
- A separate `physical_counts_bad.csv` introduces a large miscount, so the runner can be seen reporting FAIL when the data does not match the expected close.

### Hand-checked example
The close reconciles eleven SKUs against the count and posts the period's entries:

- Total book inventory = **$17,240.79**: raw material $8,167.77, packaging $7,997.18, finished goods $1,075.84. This equals the perpetual valuation tool to the cent.
- RM-HOPS counts 172 kg against a book 180 kg, an 8 kg shortage at $19.68 = a $157.44 variance, past the $50.00 tolerance, so it is flagged. RM-FININGS carries a negative on-hand flag. The exceptions list holds these two.
- Total federal excise duty = **$149.17**, equal to the excise duty engine.
- The closing entries: sales $25,435.00, cost of goods sold $5,404.81, excise duty $149.17, and a $179.38 count adjustment (the net shrinkage). Total debits = total credits = **$31,168.36**, so the books balance.

The runner (`run.py`) asserts each of these figures and prints PASS. Running it
against `physical_counts_bad.csv` prints FAIL, since the miscount raises an extra
exception.
