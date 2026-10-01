# FIFO Costing Queries

Each sale gets its first-in-first-out cost and margin from the purchase layers it drew down, and a closing proof checks that every cent purchased is either sold or still on the shelf. Purchases and sales each become intervals on a per-product cumulative-unit line, so one interval-intersection join does the whole allocation without a loop or a running count of what each layer has left. The 70-unit sale on July 10 covers units 60 to 130, across the layer boundary at 100, so it splits into 40 units at 4.00 and 30 at 4.50.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-layers.sql` | Each purchase as a cost layer with its range on the cumulative unit line. |
| `sql/02-sale-ranges.sql` | Each sale as a range on the same line, counted over units sold so far. |
| `sql/03-fifo-allocation.sql` | The engine: every sale-layer intersection with its units and cost. |
| `sql/04-sale-margins.sql` | Revenue, FIFO cost of goods sold, margin, and margin percent per sale, with a note in place of a margin on any sale the layers cannot cover. |
| `sql/05-inventory-proof.sql` | Two proofs per product: purchases equal COGS plus ending stock, and every sale found enough layer units. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/fifo-costing-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against a hand-worked example:

```
python run.py --test
```

Eleven checks cover the layer ranges, the straddling sale's exact split, both products' allocations, every margin, both proofs, and two oversold sales staying on the margin report, then print `all checks passed`.

The loader validates both CSVs before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --purchases data/invalid-purchases.csv
```

One bad row is enough to stop the run, and the message gives its number: `invalid-purchases.csv row 3: qty 0 is out of range`. The row after that has a date without zero padding, which the loader would catch next.

## How the interval trick works

A procedural FIFO walks the sales in order and depletes layers one by one. In SQL, two running sums already hold the first-in-first-out order. Stack the purchases: the first 100 beans occupy units 0 to 100 at 4.00, the next 80 occupy 100 to 180 at 4.50, the last 120 occupy 180 to 300 at 4.20. Stack the sales on the same line: 60 units take 0 to 60, the next 70 take 60 to 130, the last 90 take 130 to 220.

Now every sale draws from exactly the layers its range overlaps, and the units drawn are the intersection length, MIN of the ends minus MAX of the starts. The join condition is the standard half-open overlap test, `l.from < s.to AND s.from < l.to`, so an adjacent range that merely touches contributes nothing. Costs multiply in integer cents, and same-day rows keep their order by id.

## Costing sale 3 by hand

Sale 3 is the July 20 sale of 90 beans at 8.25. Each step ends on a figure the program prints.

1. Query 02 places it at units 130 to 220, after the 60 and 70 units sold before it.
2. Query 01 has the bean layers at 0 to 100 (4.00), 100 to 180 (4.50) and 180 to 300 (4.20).
3. The first layer fails the overlap test, because 130 < 100 is false. Sales 1 and 2 used up all 100 of its units.
4. The second layer gives MIN(180, 220) - MAX(100, 130) = 180 - 130 = 50 units, and 50 × 4.50 = 225.00.
5. The third gives MIN(300, 220) - MAX(180, 130) = 220 - 180 = 40 units, and 40 × 4.20 = 168.00.
6. Cost of goods sold is 225.00 + 168.00 = 393.00. Revenue is 90 × 8.25 = 742.50.
7. Margin is 742.50 - 393.00 = 349.50, and 349.50 / 742.50 = 0.4707, which query 04 prints as 47.1%.

Those two-argument `MIN` and `MAX` calls are SQLite's scalar forms. With two or more arguments they compare values within one row; with one argument they are the usual aggregates over many rows. Queries 04 and 05 wrap the scalar pair in `SUM` to total a sale's layers.

## The proofs

Conservation first: whatever was purchased is either sold or still on the shelf, so purchase value must equal cost of goods sold plus ending inventory, checked per product in cents. For the beans that reads 1,264.00 = 928.00 + 336.00. Ending stock falls out of the same geometry: each layer's unsold remainder is its range clipped to whatever lies past the total units sold, which leaves the beans holding 80 units of the 4.20 layer, 336.00.

Coverage second: every sale must find enough layer units. This check starts from the sales table, because a sale with no backing layers at all produces no allocation rows, and a check built on the allocations would never see it. Overselling shows up here as a FAIL naming the product, while the conservation identity keeps holding, since it only accounts for units that exist. Query 04 keeps an oversold sale on the page with its cost and margin left blank and a note counting the uncovered units, rather than pricing those units at zero.

## Sample data

Two fictional products across July 2026: three bean purchases totalling 300 units and 1,264.00, three bean sales totalling 220 units, plus two cup purchases and two cup sales. The quantities are chosen so three sales straddle layer boundaries, two land entirely inside their product's first layer, and both products end with stock on the shelf: 336.00 of beans, 30.00 of cups.

## Known limits

- Costing runs over the whole file in date order. Returns, write-offs, and negative adjustments are not modelled; they would need signed layers and change what conservation asserts.
- FIFO is an assumption about which units leave first. The same data under weighted-average costing gives different margins, and nothing here decides which policy is right.
- Same-day purchases and sales order by their id, so ids must reflect true sequence within a day.
- Prices and costs are per-unit with at most 2 decimals, held as integer cents. Unit costs with more precision, common in bulk commodities, would need a smaller money unit.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
