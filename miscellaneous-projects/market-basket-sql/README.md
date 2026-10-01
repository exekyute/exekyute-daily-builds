# Market Basket Queries

Find the product pairs that sell together more often than their popularity alone explains. A self-join counts every pair bought in the same order, support and confidence size each pair, and lift divides the count by what independent buying would produce. Espresso and croissant top the raw counts at 6 orders together yet lift to exactly 1.0, two bestsellers meeting by chance, while cold brew and cookie, together in 5, lift to 2.78.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-product-counts.sql` | How many orders hold each product, the denominators lift corrects with. |
| `sql/02-pair-counts.sql` | Every co-occurring pair counted once per order via the `a.product < b.product` self-join. |
| `sql/03-support-confidence.sql` | Support plus both directional confidences per pair. |
| `sql/04-lift.sql` | Actual versus expected co-occurrence, with an above, about, or below chance verdict. |
| `sql/05-bundle-picks.sql` | The pairs passing both gates: lift at least 1.5 and at least 3 orders together. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/market-basket-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against hand-counted answers:

```
python run.py --test
```

Eight checks cover the product counts, the pair list, the 100 percent confidence, the three key lifts, the unproven 2-order pairs, and the final picks, then print `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --lines data/invalid-lines.csv
```

Row 3 is the first to fail: `invalid-lines.csv row 3: second espresso line in order 1`. The row after that has an empty product, which the loader would catch next.

## Why raw counts mislead

Espresso is in 12 of the 20 orders. Anything popular co-occurs with it constantly, so the pair query crowns espresso and croissant the top pairing at 6 orders together. Independence would predict exactly 6: twelve twentieths of the croissant's 10 orders. Lift divides actual by expected and returns 1.0: popularity explains the whole count.

Cold brew and cookie run the other way. Six orders each, so chance predicts 1.8 together; they appear in 5, a lift of 2.78. Confidence adds direction: every one of the four muffin orders included a croissant, 100 percent, while only 40 percent of croissant orders picked up a muffin. A muffin offer belongs on the croissant order, where 6 of 10 still go without one.

## The two gates

The picks query demands lift of at least 1.5 and at least 3 orders together. Without the count gate, two tea pairs would make the list: each lifts to 1.67 on exactly 2 orders, too few to tell from chance. Three is a bar sized for a 20-order file; on twenty thousand orders it would be raised, since even strong lifts on a handful of baskets are noise.

## Croissant and muffin on a calculator

Croissant is in 10 of the 20 orders and muffin in 4 (orders 4, 5, 13 and 14), and all four muffin orders hold a croissant.

- Support is 4 / 20 = 20.0% of all orders.
- Confidence from croissant to muffin is 4 / 10 = 40.0%, and from muffin to croissant 4 / 4 = 100.0%.
- Independent buying would put them together in 10 × 4 / 20 = 2.0 orders, the expected_together column.
- Lift is 4 / 2.0 = 2.0. Query 04 gets it in one step as 4 × 20 / (10 × 4) = 80 / 40.
- Lift 2.0 clears the 1.5 gate and 4 orders clear the 3-order gate, so query 05 picks the pair.

The lift prints as 2.0, with one decimal. In SQLite, `ROUND` returns a floating-point value, and the report prints that value as it comes back; query 03's percentages go through `printf`, which fixes the number of decimals.

## Sample data

Twenty fictional cafe orders and 42 order lines across six products. The quantities are set so the biggest raw pair is pure popularity, the real bundle is second by count, one confidence hits exactly 100 percent, the espresso and tea pair falls below chance as substitutes (1 order together against 2.4 expected, lift 0.42), and two high-lift pairs fail the count gate.

## Known limits

- Everything is pairwise. Three-way bundles need a triple self-join and much more data to mean anything.
- Lift on a 20-order sample proves the mechanics, not the merchandising. The thresholds, 1.5 lift and 3 orders, are tuned to this file's size and belong higher on real volume.
- Quantities are ignored: an order with three cookies counts once for cookie. Line-level weighting is a different analysis.
- Orders are the co-occurrence unit. Baskets built per customer per day, or per session, give different pairs from the same lines.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
