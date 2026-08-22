# Price History Queries

Five SQLite queries that turn a log of product price snapshots into a versioned price history, then put it to work: the price of any product on any date, what each past order actually paid, and integrity checks for a hand-maintained price list. `LAG` flags each snapshot where the price differs from the one before it, and `LEAD` turns those change rows into `valid_from` and `valid_to` ranges, the slowly changing dimension Type 2 shape. The checks run against a deliberately broken price list and catch its overlap, its two-day gap, and its two open-ended rows.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-price-changes.sql` | The snapshots where a price moved, with the previous price and the change. Each product's first snapshot counts as a change so every product gets an opening row. |
| `sql/02-price-history.sql` | One row per price version with `valid_from`, `valid_to`, and a version number. The current version has a NULL `valid_to`. |
| `sql/03-price-as-of.sql` | Every product's price on one pinned report date. |
| `sql/04-order-repricing.sql` | Each order joined to the version that covered its date, with unit price and line total. Orders from before the first snapshot come back with a note instead of vanishing. |
| `sql/05-history-checks.sql` | Overlaps, gaps, and multiple open-ended rows in the hand-maintained price list. An empty result means the list is clean. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/price-history-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against hand-counted answers:

```
python run.py --test
```

Eleven checks cover the row counts, the change events, the full version list for the product that changed price twice, the as-of prices, every order's line total, the price list issue counts by type, and the gap detail, then print `all checks passed`.

The loader validates all three CSVs before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --snapshots data/invalid-snapshots.csv
```

It stops on the first problem and names the row: `invalid-snapshots.csv row 3: duplicate snapshot for cold-brew on 2026-07-01`. The row after that carries a negative price, which the loader would catch next.

## How the history is built

Three steps, all in `sql/02-price-history.sql`.

1. `LAG(price)` puts each snapshot's previous price beside it, per product, in date order.
2. Keep the rows where the price differs from the previous one, or where there is no previous one. Those are the change rows.
3. `LEAD(valid_from)` looks at the next change row for the same product; one day before it is this version's `valid_to`. The last version has no next row, so `DATE(NULL, '-1 day')` leaves it NULL, which reads as "still current".

```sql
history AS (
    SELECT product,
           ROW_NUMBER() OVER (PARTITION BY product ORDER BY valid_from) AS version,
           valid_from,
           DATE(LEAD(valid_from) OVER (PARTITION BY product ORDER BY valid_from), '-1 day') AS valid_to,
           price
    FROM changes
)
```

Comparing each snapshot to the previous one, rather than to a list of distinct prices, is what makes a price that reverts show up as a new version. The espresso beans go from 14.00 to 15.50 on July 11 and back to 14.00 on July 22, and the history has three versions, not two.

## Boundaries worth checking

The repricing query is where off-by-one mistakes in a date range show up, so the sample orders sit on the edges.

| Order | Date | What happens |
| --- | --- | --- |
| 1004 | 2026-07-14 | Last day of cold brew version 1, prices at 6.50 |
| 1005 | 2026-07-15 | First day of version 2, prices at 6.95 |
| 1003 | 2026-07-18 | A day with no oat milk snapshot at all, still prices at 3.25 because the version range covers it |
| 1008 | 2026-08-03 | After the last snapshot, prices at the open-ended current version |
| 1007 | 2026-06-28 | Before the first snapshot, comes back with `no price on file` |

The seven orders that price total 93.70.

## The price list checks

The history built from snapshots cannot overlap or leave gaps, because every `valid_to` is derived from the next `valid_from`. A price list that people edit by hand can do both, so the last query runs three checks on `data/price_list.csv`:

- An overlap is a self-join on the same product where a later row starts on or before an earlier row ends, with `rowid` as a tie-break so two rows that start on the same day still pair up. Open-ended rows are treated as ending on 9999-12-31, so two open rows for one product always overlap.
- A gap compares each row's `valid_from` to the furthest `valid_to` of every earlier row for that product, a running `MAX` window, so a short row nested inside a longer one cannot fake a gap.
- Multiple current rows is a plain `GROUP BY` on rows with no `valid_to`, kept when the count passes one.

On the sample list it finds four issues: the beans rows starting July 1 and July 10 overlap on the 10th, the oat milk rows leave July 27 and 28 uncovered, and oat milk has two open-ended rows, which is reported both as an overlap and as a multiple-current problem.

## Sample data

Three fictional products and 29 price snapshots on ten dates from July 1 to August 1, 2026, roughly twice a week. Oat milk has no snapshot on July 18, which is deliberate: the version range covers the day anyway. The snapshots collapse to 7 versions, 3 of them current. There are 8 orders and an 8-row hand-maintained price list with one overlap, one gap, and one product with two open rows.

## Known limits

- A change is dated to the first snapshot that showed it. With snapshots every three or four days, the real change could have happened up to three days earlier, and the history cannot know that.
- Prices are stored as `REAL`. Comparing stored values with `<>` is exact here because the same text always parses to the same float, but store cents as integers before doing arithmetic on prices in anything real.
- The overlap check reports each overlapping pair once and assumes rows are meant to be sorted by `valid_from` within a product. A row that starts before its predecessor is reported as an overlap, not reordered.
- Window functions need SQLite 3.25 or newer. The SQLite bundled with the official Python installers covers it; a Linux Python that links an old system libsqlite3 may not.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
