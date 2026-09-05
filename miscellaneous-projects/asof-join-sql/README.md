# As-Of Join Queries

Five SQLite queries that join orders to the tax rate in force on each order's date, the point-in-time lookup every rates, pricing, and FX table eventually needs. The trap comes first: joining on `effective_date <= order_date` alone turns fifteen orders into twenty-nine rows, silently drops the one order older than every rate, and reports 1,491.00 of tax where the true figure is 721.00. Then the same answer is built two correct ways, a correlated latest-date pick and a LEAD-built era table, and the build proves they agree to the cent.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-tables-shape.sql` | Both tables at a glance: order span and totals, rate versions in play. |
| `sql/02-naive-join.sql` | The trap, laid open: how many rate rows each order collects, one when right, up to three when wrong. |
| `sql/03-asof-join.sql` | Every order priced at the rate in force on its date, unpriceable ones flagged. |
| `sql/04-rate-eras.sql` | The rates as eras via LEAD, orders range-joined in, totals per era. |
| `sql/05-tax-summary.sql` | One reconciliation line: as-of versus naive, and the overstatement between them. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/asof-join-sql
python run.py
```

That prints all five reports against the sample tables. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Thirteen checks cover both boundary days, the rate cut, the dropped order, the era table, and the reconciliation, then print `all checks passed`.

The loader validates both CSVs before any query runs. Point it at the included bad rate table to see a rejection:

```
python run.py --rates data/invalid-rates.csv
```

It stops on the first problem and names the row: `invalid-rates.csv row 4: effective_date 2026-04-01 is not after the row above; one rate per date, in order, or the as-of pick is ambiguous`. Two rates effective the same day would make "the newest rate at or before this date" mean two different numbers, so the file is refused before it can.

## The trap

An effective-dated table has no foreign key to join on; the relationship is temporal. The tempting join, `ON r.effective_date <= o.order_date`, is not wrong about any single row it produces, which is what makes it dangerous: each joined row pairs an order with a rate that really was effective in its past. It is wrong about the count. An order after the second rate change matches two rates, after the third it matches three, and an aggregate downstream adds tax across all of them. Meanwhile the order older than every rate matches nothing, and an inner join drops it without a word. Query 02 prints the damage per order; query 05 totals it: 770.00 of overstatement on 721.00 of true tax.

## The as-of pick

Query 03 does it right in two moves. A correlated subquery picks the KEY of the newest rate at or before each order date, `ORDER BY effective_date DESC LIMIT 1`, and one LEFT JOIN brings back that rate's payload. LEFT matters: the pre-rate order surfaces with the note `no rate in force` and a NULL tax, rather than vanishing or, worse, defaulting to zero as if it were tax-free. The boundary is `<=`, so a rate applies from the morning of its effective date: the sample pins both sides, an order on March 31 keeping 5 percent and an order on April 1 picking up 6. A rate cut in July proves the pick takes the latest rate, never the highest.

## The era construction

Query 04 builds the same join the way a warehouse does when the per-row pick gets expensive: LEAD turns the rate list into eras, each valid from its effective date until the next one begins, the last left open-ended, and orders range-join into their era. The era totals match query 03 to the cent, 182.00 plus 264.00 plus 275.00, and the test suite asserts both constructions land on the same 721.00. When two different constructions of a temporal join agree, the calendar reading is probably right; when they disagree, one of them is quietly wrong about a boundary.

## Sample data

Fifteen orders from four fictional customers, December 2025 through September 2026, against three rate versions: 5 percent from January 1, 6 percent from April 1, 5.5 percent from July 1. Amounts are engineered so every tax figure lands on exact cents at every rate the build touches, including the naive join's inflated 11 and 16.5 percent combinations. One order predates all three rates on purpose.

## Known limits

- Dates, not timestamps. A rate that changes mid-day needs effective timestamps and the same constructions on finer grain; with dates, the whole effective day belongs to the new rate.
- One rate table for everyone. Jurisdictions mean a region column on both tables, added to the correlation in 03 and the join in 04.
- The correlated pick runs once per order row. Fine at this size and indexed by the primary key, but at warehouse scale the era table in 04 is the shape that survives, which is why the build shows it.
- Query 03 commits each row to one rounding policy, cents half away from zero, so net plus printed tax always equals printed gross. The totals in 04 and 05 round an exact sum instead, so on amounts where the tax is not exact cents the rounded pieces can differ from the rounded total by a cent; an invoicing pipeline rounds per line by declared policy and totals the lines.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
