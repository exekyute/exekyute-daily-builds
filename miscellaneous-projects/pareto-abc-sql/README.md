# Pareto ABC Queries

Revenue sorts a product catalog into classes A, B and C: A holds the products needed to reach the first 80 percent of the money, B those needed to reach 95, and C the long tail. A running window SUM down the revenue ranking, divided by a second SUM over the whole table, gives every product its cumulative share in one pass, and each class is decided on the share earned before the product. Four of the sample's twenty products earn exactly 80 percent of the revenue.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-catalog-shape.sql` | The catalog at a glance: product count, total revenue, best and worst sellers. |
| `sql/02-revenue-ranking.sql` | Every product ranked, with its individual slice of the total. |
| `sql/03-cumulative-share.sql` | Running revenue and cumulative share down the ranking, the construction laid open. |
| `sql/04-abc-classes.sql` | Each product classed A, B, or C on the share accumulated before it. |
| `sql/05-class-summary.sql` | One line per class: how much of the catalog, how much of the money. |

## Running it

Python 3 runs it, using only the standard library.

```
cd miscellaneous-projects/pareto-abc-sql
python run.py
```

That runs the five reports on the sample catalog. To check the queries against hand-computed answers instead:

```
python run.py --test
```

Fifteen checks: the totals, the tiebreak, exact landings on both sides of both boundaries, and the full class roll-up. A passing run prints `all checks passed`.

Before any query runs, the loader checks the CSV. The included bad file shows a rejection:

```
python run.py --products data/invalid-products.csv
```

It refuses the file at its first problem and gives the row: `invalid-products.csv row 4: revenue '-25.00' is negative; net returns out of revenue before ranking`. Negative revenue is refused because the method needs a running share that only climbs. One negative row shrinks the total everything is measured against, the cumulative percentage overshoots one hundred partway down and falls back, and a class boundary that can be crossed from both directions stops meaning anything.

## The running share

The running total is a window SUM ordered down the ranking, and the grand total it divides by is another window SUM over the whole table, so one pass produces both: `SUM(revenue_cents) OVER (ORDER BY revenue_cents DESC, product ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)` against `SUM(revenue_cents) OVER ()`. The query plan has a single scan of the products table, and nothing joins back to a totals subquery.

Ties need care twice over. Ordered by revenue alone, the default RANGE frame treats tied rows as peers and folds them into one block: both of the sample's 60.00 products would print a running share of 99.95, each including the other. The product-name tiebreak makes the ordering total, which by itself prevents that merge, since RANGE peers must match on every ORDER BY term. The explicit ROWS frame states the one-row-at-a-time intent and gives tied rows separate running totals even in a variant where the tiebreak gets dropped.

Down the actual ranking the tied rows climb 99.89 then 99.95, and every rank is reproducible run to run. Revenue is held as integer cents, so the running totals are exact; the dollar columns shift cents back to dollars, and the only lossy rounding is at the percentages.

## The boundaries

A product is an A if it is needed to reach the first 80 percent of revenue, a B if needed to reach 95, a C after that. Needed means the test runs on the share accumulated before the product, not after it: the same running SUM with its frame ended one row earlier, `ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING`. On the before-share the best seller always starts at zero, so rank one is an A on any catalog.

Testing each product's own cumulative share instead fails on a skewed catalog. Give the best seller 96 percent of revenue and its own share is already past both boundaries. Classed on that share it becomes a C, the A class is empty, and on that catalog all twenty products come out C. The last change in the table below builds exactly that catalog.

The sample pins the boundary behaviour down on both sides. Rank four starts at 70 and lands on exactly 80.00: an A, because it was needed to get there. Rank five starts at exactly 80.00: the first B. Rank seven reaches exactly 95.00 and stays a B; rank eight starts there and opens C. The before-share is rounded to the same two decimals the report prints, so every class agrees with a number visible on the page.

## Change one row

Each row below is a separate edit to `data/products.csv`, made on the original file; queries 04 and 05 show what moves.

| Change | What moves |
| --- | --- |
| `Pour Over Kit,6000.00` to `Pour Over Kit,6100.00` | The total grows to 100,100.00, so the 80,000.00 ahead of rank five is now 79.92 percent and Pour Over Kit turns from B to A. Query 05 reads A: 5 products and 86.01 percent of revenue, B: 2. |
| `Coffee Beans 1kg,14000.00` to `Coffee Beans 1kg,13900.00` | Two other products move up a class without selling any more: Pour Over Kit to A at a before-share of 79.98, and Travel Mug to B at 94.99. |
| `Espresso Machine,32000.00` to `Espresso Machine,1632000.00` | One product now earns 96.0 percent. It starts at 0.0 and stays an A, every other product starts at 96.0 or more and is a C, and query 05 prints no B line at all. |

## Sample data

Twenty products of a fictional coffee-gear shop, revenue summing to exactly 100,000.00 and chosen for checking by hand: each product's share reads straight off its revenue, 32,000.00 is 32 percent, and the running shares land on round numbers at both class boundaries. A tie at 60.00 tests the tiebreak. Four products carry eighty percent of the revenue; the bottom thirteen together carry five.

## Known limits

- The 80 and 95 cutoffs are constants in two SQL files, and they class the rounded before-share, so a product starting at a true 79.996 percent rounds to 80.0 and lands in B. A share sitting on a half rounds by its stored float and by SQLite version: 80.005 is stored a hair under the half, which SQLite 3.50 rounds to 80.0 and 3.31 and 3.34 round to 80.01. On any one version every verdict matches a printed number. A boundary that must be exact wants the comparison moved to unrounded cents.
- A tie that straddles a boundary is split alphabetically. Two products tied in revenue where the running share crosses 80 between them will land in different classes by name order; a real catalog wants a business tiebreak, oldest SKU or highest margin, before the alphabet decides.
- One period, one metric. ABC per quarter or per region means PARTITION BY on both window SUMs, and the classification follows unchanged.
- Zero-revenue products are legal and always class C, and they inflate the product counts: a catalog padded with dead SKUs makes the A class's share of the catalog look even leaner than it really is.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
