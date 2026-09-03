# Pareto ABC Queries

Five SQLite queries that rank a product catalog by revenue, carry a running share of the total down the ranking, and cut the catalog into A, B, and C: the handful of products that earn most of the money, the middle, and the long tail. On the sample catalog the cut lands on the textbook Pareto sentence: four of twenty products, twenty percent of the catalog, earn exactly eighty percent of the revenue.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-catalog-shape.sql` | The catalog at a glance: product count, total revenue, best and worst sellers. |
| `sql/02-revenue-ranking.sql` | Every product ranked, with its individual slice of the total. |
| `sql/03-cumulative-share.sql` | Running revenue and cumulative share down the ranking, the construction laid open. |
| `sql/04-abc-classes.sql` | Each product classed A, B, or C on the share accumulated before it. |
| `sql/05-class-summary.sql` | One line per class: how much of the catalog, how much of the money. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/pareto-abc-sql
python run.py
```

That prints all five reports against the sample catalog. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Fifteen checks cover the totals, the tiebreak, exact landings on both sides of both boundaries, and the full class roll-up, then print `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --products data/invalid-products.csv
```

It stops on the first problem and names the row: `invalid-products.csv row 4: revenue '-25.00' is negative; net returns out of revenue before ranking`. Negative revenue is refused rather than absorbed because the build rests on a running share that only climbs: one negative row shrinks the total everything is measured against, the cumulative percentage overshoots one hundred partway down and falls back, and a class boundary that can be approached from both directions stops meaning anything.

## The running share

The running total is a window SUM ordered down the ranking, and the grand total it divides by is another window SUM over the whole table, so one pass produces both: `SUM(revenue_cents) OVER (ORDER BY revenue_cents DESC, product ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)` against `SUM(revenue_cents) OVER ()`. No second scan, no join back to a totals subquery.

Ties need care twice over. Ordered by revenue alone, the default RANGE frame treats tied rows as peers and folds them into one block: both of the sample's 60.00 products would print the same running share, each including the other. The product-name tiebreak makes the ordering total, which by itself prevents that merge, since RANGE peers must match on every ORDER BY term; the explicit ROWS frame states the one-row-at-a-time intent and keeps the running column honest even in a variant where the tiebreak gets dropped. Down the actual ranking the tied rows climb 99.89 then 99.95, and every rank is reproducible run to run.

Revenue is held as integer cents, so the running totals are exact; the dollar columns just shift cents back to dollars, and the only lossy rounding is at the percentages.

## The boundaries

A product is an A if it is needed to reach the first 80 percent of revenue, a B if needed to reach 95, a C after that. Needed means the test runs on the share accumulated before the product, not after it: the same running SUM with its frame ended one row earlier, `ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING`. Testing each product's own cumulative share instead is the classic ABC mistake, and it fails on the most plausible skewed catalog there is: a best seller that alone carries 96 percent of revenue starts above both boundaries and gets silently classed C, leaving the A class empty. On the before-share the best seller always starts at zero, so rank one is an A on any catalog.

The sample pins the boundary behaviour down on both sides. Rank four starts at 70 and lands on exactly 80.00: an A, because it was needed to get there. Rank five starts at exactly 80.00: the first B. Rank seven reaches exactly 95.00 and stays a B; rank eight starts there and opens C. The before-share is rounded to the same two decimals the report prints, so every class agrees with a number visible on the page.

## Sample data

Twenty products of a fictional coffee-gear shop, revenue summing to exactly 100,000.00 and engineered for hand-checking: each product's share reads straight off its revenue, 32,000.00 is 32 percent, and the running shares land on round numbers at both class boundaries. A planted tie at 60.00 exercises the tiebreak. Four products carry eighty percent of the revenue; the bottom thirteen together carry five.

## Known limits

- The 80 and 95 cutoffs are constants in two SQL files, and they class the rounded before-share: a product starting at a true 79.996 percent rounds to 80.0 and lands in B, and float halfway values round down, 80.005 stores as a hair under and prints 80.0. That keeps every verdict identical to a printed number; a boundary that must be exact wants the comparison moved to unrounded cents.
- A tie that straddles a boundary is split alphabetically. Two products tied in revenue where the running share crosses 80 between them will land in different classes by name order; a real catalog wants a business tiebreak, oldest SKU or highest margin, before the alphabet decides.
- One period, one metric. ABC per quarter or per region means PARTITION BY on both window SUMs, and the classification follows unchanged.
- Zero-revenue products are legal and always class C, and they inflate the product counts: a catalog padded with dead SKUs makes the A class's share of the catalog look even leaner than it really is.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
