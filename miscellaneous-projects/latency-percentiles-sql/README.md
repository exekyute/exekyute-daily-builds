# Latency Percentile Queries

How slow each API endpoint is at p50, p90, and p99 comes straight out of a raw request log, interpolated the way `PERCENTILE_CONT` defines it in engines that have the function. The position math is one line: percentile p sits at rank 1 + p times (n - 1), and a fractional rank blends the two neighbouring values linearly. Search averages 133.5 ms on the sample while its p99 is 800, because two slow requests, at 400 and 900 ms, hide inside the mean.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-endpoint-summary.sql` | Counts, min, mean, max per endpoint. The mean is the number the rest of the set argues with. |
| `sql/02-ranked-durations.sql` | Every request ranked inside its endpoint, the scaffold the percentiles stand on. |
| `sql/03-percentile-math.sql` | The interpolation laid open: bracket values, blend fraction, and result for each percentile. |
| `sql/04-percentile-grid.sql` | One row per endpoint: mean beside p50, p90, p99, so the gap is visible at a glance. |
| `sql/05-slowest-requests.sql` | The three slowest requests per endpoint with their timestamps, the rows an on-call engineer opens next. |

## Running it

Install nothing beyond Python 3: the runner uses only the standard library.

```
cd miscellaneous-projects/latency-percentiles-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Nine checks back the reports: the 36 loaded requests, the three endpoint summaries, the tied 80 ms pair under the search median, the 9 percentile rows, the blends behind search p99 (400 to 900 at 0.8), login p99 (0.9 of the way from 50 to 250) and export p50 (the 0.5 midpoint, 1500), the full grid, and the three slowest requests per endpoint. When all nine hold, the run prints `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --requests data/invalid-requests.csv
```

Row 3 is as far as it gets: `invalid-requests.csv row 3: duration_ms 'fast' is not an integer`. The row after that has a timestamp without zero padding, which the loader would catch next.

## The position math

Rank every duration inside its endpoint, count the rows, and the percentile p lives at 1-based position 1 + p times (n - 1). A whole-number position is just that row. A fractional one blends the rows either side: with 21 search requests, p99 lands at position 20.8, so the answer is the 20th value plus 0.8 of the way to the 21st, 400 + 0.8 x 500 = 800. `CAST` truncates the position down to the lower rank, which is the floor for positive numbers, and a two-argument `MIN` caps the upper rank at n so an exact landing never reaches past the last row.

SQLite 3.50.4 (through Python's `sqlite3` module), 3.34.0 and 3.31.1 all answer `percentile_cont` with `no such function`, so the formula is written out in SQL rather than called.

The sample sizes are chosen to exercise both paths. Search (n = 21) puts p50 and p90 exactly on ranks 11 and 19, and rank 11 sits on a pair of tied 80 ms requests, which interpolation is indifferent to. Login (n = 11) blends its p99 at 0.9 between 50 and 250, landing on 230.

## Mean and tail on login and search

Login's mean is 58.4 ms, but half its requests finish in 40 ms or less; a single 250 ms request does the damage. Search is worse: the mean says 133.5 ms, the median says 80, and the p99 says 800. Averages fold the tail into the middle, percentiles keep them apart, and the slowest-requests query then names the exact rows behind the tail.

## Sample data

Three fictional endpoints and 36 requests across one day, August 20, 2026: 21 search, 11 login, 4 export. The export endpoint is kept tiny on purpose: its p99 of 1988 ms interpolates between the 3rd and 4th of four requests, which is arithmetic, not evidence.

## Known limits

- Percentiles on four requests are noise. The formula computes them anyway; a real dashboard should suppress percentiles under a minimum sample size.
- Which of two tied durations gets which rank is unspecified. The interpolated value is unaffected, since equal values blend to themselves.
- The whole log computes as one window, so a bad hour dissolves into the day. Per-hour percentiles mean adding the hour to both PARTITION BY clauses.
- This is the `PERCENTILE_CONT` definition. `PERCENTILE_DISC` and nearest-rank methods return actual observed values instead of blends, and on small samples their p99s differ noticeably from these.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
