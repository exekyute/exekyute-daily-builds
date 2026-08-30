# FIFO Costing Queries

Five SQLite queries that cost every sale against purchase layers in first-in-first-out order, with no loops and no depletion state: purchases and sales each become intervals on a per-product cumulative-unit line, and one interval-intersection join does the entire allocation. The 70-unit sale on July 10 splits into 40 units at 4.00 and 30 at 4.50 because its range, units 60 to 130, straddles the layer boundary at 100. A closing proof shows every cent purchased is either sold or still on the shelf: 1,264.00 = 928.00 + 336.00 for the beans, to the cent.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-layers.sql` | Each purchase as a cost layer with its range on the cumulative unit line. |
| `sql/02-sale-ranges.sql` | Each sale as a range on the same line, counted over units sold so far. |
| `sql/03-fifo-allocation.sql` | The engine: every sale-layer intersection with its units and cost. |
| `sql/04-sale-margins.sql` | Revenue, FIFO cost of goods sold, margin, and margin percent per sale. |
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

Ten checks cover the layer ranges, the straddling sale's exact split, both products' allocations, every margin, and both proofs, then print `all checks passed`.

The loader validates both CSVs before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --purchases data/invalid-purchases.csv
```

It stops on the first problem and names the row: `invalid-purchases.csv row 3: qty 0 is out of range`. The row after that has a date without zero padding, which the loader would catch next.

## How the interval trick works

The usual FIFO implementation walks sales in order and depletes layers one by one, which is procedural code. The relational version notices that first-in-first-out is already encoded by two running sums. Stack the purchases: the first 100 beans occupy units 0 to 100 at 4.00, the next 80 occupy 100 to 180 at 4.50, the last 120 occupy 180 to 300 at 4.20. Stack the sales on the same line: 60 units take 0 to 60, the next 70 take 60 to 130, the last 90 take 130 to 220.

Now every sale draws from exactly the layers its range overlaps, and the units drawn are the intersection length, MIN of the ends minus MAX of the starts. The join condition is the standard half-open overlap test, `l.from < s.to AND s.from < l.to`, so an adjacent range that merely touches contributes nothing. Costs multiply in integer cents, and same-day rows keep their order by id.

## The proofs

Conservation first: whatever was purchased is either sold or still on the shelf, so purchase value must equal cost of goods sold plus ending inventory, checked per product in cents. Ending stock falls out of the same geometry: each layer's unsold remainder is its range clipped to whatever lies past the total units sold, which leaves the beans holding 80 units of the 4.20 layer, 336.00.

Coverage second: every sale must find enough layer units. This check deliberately starts from the sales table, because a sale with no backing layers at all produces no allocation rows, and a check built on the allocations would never see it. Overselling shows up here as a FAIL naming the product, while the conservation identity keeps holding, since it only accounts for units that exist.

## Sample data

Two fictional products across July 2026: three bean purchases totalling 300 units and 1,264.00, three bean sales totalling 220 units, plus two cup purchases and two cup sales. The quantities are chosen so three sales straddle layer boundaries, two land entirely inside their product's first layer, and both products end with stock on the shelf: 336.00 of beans, 30.00 of cups.

## Known limits

- Costing runs over the whole file in date order. Returns, write-offs, and negative adjustments are not modelled; they would need signed layers and change what conservation asserts.
- FIFO is a flow assumption, not a discovery. The same data under weighted-average costing gives different margins, and nothing here decides which policy is right.
- Same-day purchases and sales order by their id, so ids must reflect true sequence within a day.
- Prices and costs are per-unit with at most 2 decimals, held as integer cents. Unit costs with more precision, common in bulk commodities, would need a smaller money unit.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
