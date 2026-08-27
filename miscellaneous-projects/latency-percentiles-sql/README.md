# Latency Percentile Queries

Five SQLite queries that compute interpolated p50, p90, and p99 latencies per API endpoint from a raw request log, using the definition `PERCENTILE_CONT` implements in engines that have it, which SQLite does not. The position math is one line: percentile p sits at rank 1 + p times (n - 1), and a fractional rank blends the two neighbouring values linearly. The payoff is in the grid: search averages 133.5 ms while its p99 is 800, because two slow requests hide inside a healthy-looking mean.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-endpoint-summary.sql` | Counts, min, mean, max per endpoint. The mean is the number the rest of the set argues with. |
| `sql/02-ranked-durations.sql` | Every request ranked inside its endpoint, the scaffold the percentiles stand on. |
| `sql/03-percentile-math.sql` | The interpolation laid open: bracket values, blend fraction, and result for each percentile. |
| `sql/04-percentile-grid.sql` | One row per endpoint: mean beside p50, p90, p99, so the gap is visible at a glance. |
| `sql/05-slowest-requests.sql` | The three slowest requests per endpoint with their timestamps, the rows an on-call engineer opens next. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/latency-percentiles-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Nine checks cover the summaries, the tie under the search median, every interpolation bracket, the full grid, and the slowest-request rankings, then print `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --requests data/invalid-requests.csv
```

It stops on the first problem and names the row: `invalid-requests.csv row 3: duration_ms 'fast' is not an integer`. The row after that has a timestamp without zero padding, which the loader would catch next.

## The position math

Rank every duration inside its endpoint, count the rows, and the percentile p lives at 1-based position 1 + p times (n - 1). A whole-number position is just that row. A fractional one blends the rows either side: with 21 search requests, p99 lands at position 20.8, so the answer is the 20th value plus 0.8 of the way to the 21st, 400 + 0.8 x 500 = 800. `CAST` truncates the position down to the lower rank, which is the floor for positive numbers, and a two-argument `MIN` caps the upper rank at n so an exact landing never reaches past the last row.

The sample sizes are chosen to exercise both paths. Search (n = 21) puts p50 and p90 exactly on ranks 11 and 19, and rank 11 sits on a pair of tied 80 ms requests, which interpolation is indifferent to. Login (n = 11) blends its p99 at 0.9 between 50 and 250, landing on 230.

## Why the mean lies

Login's mean is 58.4 ms, but half its requests finish in 40 ms or less; a single 250 ms request does the damage. Search is worse: the mean says 133.5 ms, the median says 80, and the p99 says 800. Averages fold the tail into the middle, percentiles keep them apart, and the slowest-requests query then names the exact rows behind the tail.

## Sample data

Three fictional endpoints and 36 requests across one day, August 20, 2026: 21 search, 11 login, 4 export. The export endpoint is deliberately tiny: its p99 of 1988 ms interpolates between the 3rd and 4th of four requests, which is arithmetic, not evidence.

## Known limits

- Percentiles on four requests are noise. The formula computes them anyway; a real dashboard should suppress percentiles under a minimum sample size.
- Which of two tied durations gets which rank is unspecified. The interpolated value is unaffected, since equal values blend to themselves.
- The whole log computes as one window, so a bad hour dissolves into the day. Per-hour percentiles mean adding the hour to both PARTITION BY clauses.
- This is the `PERCENTILE_CONT` definition. `PERCENTILE_DISC` and nearest-rank methods return actual observed values instead of blends, and on small samples their p99s differ noticeably from these.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
