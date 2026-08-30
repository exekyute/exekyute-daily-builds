# RFM Scoring Queries

Five SQLite queries that score every customer on recency, frequency, and monetary value with `NTILE` quintiles, then turn the three-digit codes into named segments a retention plan can act on. `NTILE`'s sharp edge is the lesson: it deals rows into equal buckets and does not care about ties, so two customers with identical order counts can score differently, and every `ORDER BY` here carries a tiebreak so even that arbitrariness is at least deterministic. On the sample book, three champions carry 49.3 percent of revenue, and the single quiet big spender carries more than the loyal and regular tiers together.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-customer-summary.sql` | Orders, last order, days since, and total spend per customer, the three facts RFM is named after. |
| `sql/02-rfm-scores.sql` | The quintile scores per dimension and the combined code, 555 down to 111. |
| `sql/03-ntile-mechanics.sql` | The frequency ranking laid open, with every tied-but-split customer marked. |
| `sql/04-segments.sql` | Codes into words: champions, loyal, big spender at risk, at risk, regular, lost. |
| `sql/05-segment-rollup.sql` | Headcount, revenue, revenue share, and days since last order per segment. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/rfm-scoring-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against hand-counted answers:

```
python run.py --test
```

Nine checks cover the summaries, every RFM code, the tie splits, the segment map, and the full rollup, then print `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --orders data/invalid-orders.csv
```

It stops on the first problem and names the row: `invalid-orders.csv row 3: amount '45.005' has more than 2 decimal places`. The row after that has a date without zero padding, which the loader would catch next.

## How NTILE deals the buckets

Ten customers into five buckets is two per bucket, dealt in sorted order, and the bucket boundary falls wherever it falls. The sample plants three tied pairs to make the consequence visible: dev and eli both placed two orders, yet dev scores F1 and eli F2, because the boundary runs between them and the customer_id tiebreak decided who stood on which side. The same split happens to fay and hana at three orders and to gus and jon at four. When the row count does not divide evenly, SQLite hands the earlier buckets the extra members, so the best bucket is never the padded one under an ascending sort.

That tiebreak matters more than it looks. Without a unique column in the `ORDER BY`, tied rows land in buckets in whatever order the engine visits them, and the same query can hand a customer a different score on a different day.

## Scores into segments

The CASE reads top down, most specific first. Strong on all three dimensions is a champion. Strong recency and frequency with lighter spend is loyal. Heavy spend gone quiet, like hana at 335, is the big spender at risk, the customer worth a phone call this week, while heavy spend still current keeps a plain big spender tier so it can never fall through to regular. Then the fading tiers by recency alone: 2 is at risk, 1 is lost, and whatever remains is regular.

## Sample data

Ten fictional customers and 38 orders from May 2 to August 28, 2026, worth 3,030.00 in total, scored against a pinned report date of 2026-08-30. The quantities plant three frequency ties on bucket boundaries, one heavy spender whose last order is a month old, and a customer gone 120 days.

## Known limits

- Quintile scores are relative. They compare customers to the rest of this book, not to any absolute standard, so the same customer scores differently in a different crowd.
- Ties split by customer_id, arbitrary but stable. Percentile-rank scoring would keep tied customers together at the cost of unequal buckets.
- The report date is pinned in two SQL files. Swap it for `DATE('now')` against live data.
- The segment map is one reasonable cut. RFM practice carries dozens of them, and none is canonical, so the CASE is the part to argue with.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
