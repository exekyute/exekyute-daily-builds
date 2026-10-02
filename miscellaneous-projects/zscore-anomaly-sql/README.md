# Z-Score Anomaly Queries

Any day of a shop's order counts that lands two or more standard deviations from the 14 days before it gets a flag, and so does any day whose baseline never moved. SQLite has no standard-deviation function, so the queries build one from window averages, the mean of the squares less the square of the mean, over a frame that ends the day before so a spike stays out of the baseline it is judged against. The sample's planted promotion scores exactly 6.0, the planted outage -3.46, and a fortnight of identical days gets a flat-baseline flag where a score would divide by zero.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-series-shape.sql` | The series at a glance: span, overall mean, extremes with dates. |
| `sql/02-rolling-baseline.sql` | Each day's trailing mean and sigma, the STDEV construction laid open. |
| `sql/03-z-scores.sql` | Every fully-windowed day scored, with anomaly and flat-baseline flags. |
| `sql/04-anomalies.sql` | Just the flagged days: spikes, drops, and flat baselines. |
| `sql/05-anomaly-context.sql` | Each flagged day beside the two-sigma band it broke, the line an incident note quotes. |

## Running it

`run.py` needs Python 3 and no third-party packages.

```
cd miscellaneous-projects/zscore-anomaly-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

There are thirteen checks, among them the empty first window, the exact baseline of mean 100 and sigma 5, all three flagged days, two of the three lines in query 05, and a copy of the series with the promotion cut to 110, which sits exactly on the band edge. With none failing, the last line is `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --metrics data/invalid-metrics.csv
```

The message names the row it stopped at: `invalid-metrics.csv row 4: dates must be consecutive; expected 2026-07-22`. `ROWS` windows count rows, and with a date missing, a 14-row window covers more than 14 days without any sign of it. That is why the loader refuses gaps outright.

## Standard deviation from window averages

Population variance is the mean of the squares minus the square of the mean, and windows compute both parts directly: `AVG(orders * orders) OVER w - AVG(orders) OVER w * AVG(orders) OVER w`, with sigma as its square root. The frame is `ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING`: fourteen rows of history, current day out.

The first fourteen days have no full window and are not scored. Scoring them would flag an ordinary day. July 21 has a one-day window and a sigma of 0, so it would come out as a flat baseline.

The sample's baseline is built for checking by hand: days alternating 95 and 105 give a trailing mean of exactly 100 and a population sigma of exactly 5, so the 130-order promotion day is 30 over the mean and exactly 6.0 sigma out. The 70-order outage a week later is scored against a window that still holds the spike. Its baseline mean is 101.79 and its sigma 9.18, both pushed up by the anomaly before it, and the drop still clears the threshold at -3.46.

## The flat baseline

Fourteen identical days at the end of the series give the next day a sigma of zero, and a z-score with a zero denominator is undefined. `NULLIF` turns the zero into NULL, so the score comes out NULL and the flag names the condition. A baseline that never moved deserves a look in its own right, for example for a frozen pipeline.

SQLite would return NULL here without the `NULLIF` as well. It answers any division by zero with NULL and raises no error, so the `NULLIF` is there to make the intent readable.

## Poke at the series

Make each edit on a fresh copy of `data/daily_metrics.csv`, then run `python run.py`:

1. Change `2026-08-10,130` to `2026-08-10,109`. The promotion now scores 1.8 and drops out of query 04. The outage on August 17 scores -5.63 instead of -3.46. Its window still holds August 10, but at 109 that day inflates the window's sigma far less: 5.38 where it was 9.18.
2. Change `2026-08-25,100` to `2026-08-25,101`. The window behind September 1 now has a little spread, a sigma of 0.26, so that day is scored at -0.28 and loses its flat-baseline flag. Queries 04 and 05 list two days.

## Sample data

Forty-four consecutive days, July 20 to September 1, 2026, of a fictional shop's daily order counts: an alternating 95/105 baseline, a 130 spike on August 10, a 70 drop on August 17, and a constant 100 from August 18 on. Thirty days carry full windows and are scored, and three of them are flagged.

## Known limits

- Z-scores catch jumps. A drift keeps raising its own baseline: a series that climbs by the same amount every day scores 1.86 on every scored day, whatever the step, and never reaches the threshold of 2. Five percent a week, compounded daily, from 1,000 orders a day scores between 1.88 and 1.92 over 120 days and is never flagged; from 100 a day, rounding to whole orders tips 7 of the 106 scored days to 2 or more. Catching a drift takes a different method.
- The variance is population variance over exactly 14 days. The mean-of-squares construction cancels badly once values grow past the point where their squares stay exact, so the loader caps daily counts below ten million and the queries clamp variance at zero; at larger scales a two-pass variance is the right tool.
- The 14-day window is a constant in four SQL files and the two-sigma threshold in three, tuned to a daily retail series. A noisy metric wants a wider band before anyone gets paged.
- One metric per file. Scoring several series means adding the metric name to the window's PARTITION BY.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
