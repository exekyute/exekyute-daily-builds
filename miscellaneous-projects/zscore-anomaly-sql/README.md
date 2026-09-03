# Z-Score Anomaly Queries

Five SQLite queries that score every day of a metric series against its own recent past and flag the ones worth waking someone for. SQLite has no STDEV, so the standard deviation is built from first principles: variance as the mean of squares minus the square of the mean, sigma as its square root, over a window of the 14 days before each day with the day itself excluded, so a spike cannot dilute the very baseline it is judged against. On the sample series the planted promotion scores exactly 6.0 sigma, the planted outage lands at -3.46, and a fortnight of identical days produces the zero-sigma edge case the query names instead of dividing by.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-series-shape.sql` | The series at a glance: span, overall mean, extremes with dates. |
| `sql/02-rolling-baseline.sql` | Each day's trailing mean and sigma, the STDEV construction laid open. |
| `sql/03-z-scores.sql` | Every fully-windowed day scored, with anomaly and flat-baseline flags. |
| `sql/04-anomalies.sql` | Just the flagged days: spikes, drops, and flat baselines. |
| `sql/05-anomaly-context.sql` | Each flagged day beside the two-sigma band it broke, the line an incident note quotes. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/zscore-anomaly-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Twelve checks cover the window sizes, the exact mean-100-sigma-5 baseline, all three flagged days, and both context bands, then print `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --metrics data/invalid-metrics.csv
```

It stops on the first problem and names the row: `invalid-metrics.csv row 4: dates must be consecutive; expected 2026-07-22`. The gap check exists because `ROWS` windows count rows, not days: with missing dates, a 14-row window silently stops meaning 14 days, so the loader refuses gaps outright.

## Building STDEV from nothing

Population variance is the mean of the squares minus the square of the mean, which windows compute directly: `AVG(orders * orders) OVER w - AVG(orders) OVER w * AVG(orders) OVER w`, and sigma is the square root. The window frame is `ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING`: fourteen rows of history, current day out. The first fourteen days have no full window and are not scored at all, which is the honest choice; scoring against a half-window flags the ordinary as strange.

The sample's baseline is engineered for hand-checking: days alternating 95 and 105 give a trailing mean of exactly 100 and a population sigma of exactly 5, so the 130-order promotion day is 30 over the mean and exactly 6.0 sigma out. The 70-order outage a week later scores against a window that contains the spike, which is the subtle part: its baseline mean is 101.79 and its sigma 9.18, both inflated by the anomaly before it, and the drop still clears the threshold at -3.46.

## The flat baseline

Fourteen identical days at the end of the series give the next day a sigma of zero, and a z-score with a zero denominator is not a big number, it is undefined. `NULLIF` turns the zero into NULL so the score rides along as NULL, and the flag names the condition: a baseline that never moved is its own kind of signal, worth a look for a frozen pipeline rather than a divide-by-zero crash.

## Sample data

Forty-four consecutive days, July 20 to September 1, 2026, of a fictional shop's daily order counts: an alternating 95/105 baseline, a 130 spike on August 10, a 70 drop on August 17, and a constant 100 from August 18 on. Thirty days carry full windows and are scored; exactly three get flagged.

## Known limits

- Z-scores catch jumps, not drifts. A metric creeping up five percent a week keeps refreshing its own baseline and never trips the threshold; drift detection is a different tool.
- The variance is population variance over exactly 14 days. The mean-of-squares construction cancels badly once values grow past the point where their squares stay exact, so the loader caps daily counts below ten million and the queries clamp variance at zero; at genuinely larger scales a two-pass variance is the right tool.
- The 14-day window is a constant in four SQL files and the two-sigma threshold in three, tuned to a daily retail series. A noisy metric wants a wider band before anyone gets paged.
- One metric per file. Scoring several series means adding the metric name to the window's PARTITION BY.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
