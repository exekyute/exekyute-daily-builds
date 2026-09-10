# Forward-Fill Queries

Five SQLite queries that fill the gaps in a cold-storage sensor log with the last reading carried forward, then mark where a carried value has gone stale. The obvious fill, `COALESCE(tenths, LAG(tenths))`, handles a single missing reading and leaves the rest of each run blank, filling four of the twelve gaps that have an earlier reading to carry, where a running COUNT fills all twelve. A two-hour staleness cap then shows what a carried value can hide: the cooler went dark for six hours, forward fill reports a steady 3.5 degrees throughout, and the next real reading is 6.8, over its 4.0 limit.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-log-shape.sql` | Each sensor at a glance: its limit, rows logged, readings measured, readings missing. |
| `sql/02-lag-falls-short.sql` | Every fillable gap, what LAG puts there, and what the last real reading was. |
| `sql/03-forward-fill.sql` | Every row filled in one pass, with the reading it came from and how old that reading is. |
| `sql/04-staleness-cap.sql` | Per sensor: rows measured, filled, too stale to fill, and before any reading. |
| `sql/05-blind-spots.sql` | Each stretch nobody can vouch for, stale or dark from the start, and the first real reading after it. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.25 or newer for window functions.

```
cd miscellaneous-projects/forward-fill-sql
python run.py
```

That prints all five reports against the sample log. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Twelve checks cover the LAG shortfall, the counter, a three-row run and its ageing, the leading gap, agreement between the one-pass and correlated fills, the four-way split, all three blind spots, and a separate uneven log proving the cap runs on the clock, then print `all checks passed`.

The loader validates both CSVs before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --readings data/invalid-readings.csv
```

It stops on the first problem and names the row: `invalid-readings.csv row 4: CLR-1 already has a row at 2026-09-09 01:00; the last reading before any later moment would be ambiguous`. Two rows for one sensor at one instant would give "the most recent reading" two values, so a sensor gets one row per moment.

## Why LAG falls short

LAG reaches exactly one row back. For a missing reading after a real one it returns that reading, which is right, and for the second row of a run it looks back at an empty row and returns NULL. So `COALESCE(tenths, LAG(tenths))` either returns the correct value or leaves the row blank, and it can never return a wrong number, which is what makes it easy to trust.

Query 02 shows the cost across the sample: twelve gaps have an earlier reading to carry, and LAG fills four of them.

`LAST_VALUE` looks like the fix and is not one. Over a frame running from the first row to the current one, it returns the current row's value, and the current row is the empty one. The standard answer, `LAG(tenths) IGNORE NULLS`, is a syntax error in SQLite.

The last_reading column in query 02 is the honest answer, found by a correlated subquery that searches backwards for each row. It is correct, and it walks the primary-key index back only as far as the nearest real reading, so each missing row costs its distance back to the start of its own dark run. Summed over a run, that grows with the square of the run's length, which stays negligible for short runs and turns heavy only where a sensor stays dark for a long stretch.

## The COUNT trick

`COUNT(tenths)` skips NULLs, so a running `COUNT(tenths) OVER (PARTITION BY sensor_id ORDER BY reading_at)` is a counter that advances only when a real reading arrives. Query 03 prints it as `readings_so_far`, and on the freezer it reads 1, 2, 2, 3, 3, 3, 3, 4, 5, 5, 5, 6: every missing row shares its number with the last real reading before it.

That number becomes a group key. Every group except group zero holds exactly one real reading, the one that advanced the counter, so `MAX(tenths) OVER (PARTITION BY sensor_id, readings_so_far)` returns it for every row in the group. Rows before a sensor's first reading sit in group zero, which holds no reading, and correctly get nothing.

The same group also yields when that reading was taken, though only through a mask: every row carries a timestamp, so a bare MAX would return the latest row in the group, and `CASE WHEN tenths IS NOT NULL` keeps just the reading's own. The test suite checks that this one-pass fill matches the correlated subquery from query 02 on every fillable gap.

## The staleness cap

A carried value is a measurement for a while and a guess after that. Query 04 draws the line at two hours, measured on the clock from each carried reading's own timestamp rather than counted in rows, so an unevenly spaced log is judged by the age of the reading and not by how many polls went by. The sample is polled hourly, where the two would always agree, so the test suite also runs query 04 against a three-row log with uneven polls and confirms that a row only two rows after its reading is already too stale. Across the sample's twenty-four rows that gives ten measured, seven filled, five too stale to fill, and two before any reading at all.

Query 05 turns every unvouched stretch into a window and checks the first real reading after each one. A too-stale window is the part of a run after its carried reading passes the cap, and a dark start is the run before a sensor's first reading, when there is nothing to carry at all. The freezer has one too-stale row at 06:00, followed by -17.6, well inside its -15.0 limit.

The cooler has both kinds. Its dark start covers 00:00 and 01:00 and ends on 3.4, within limit, while its too-stale window runs from 06:00 through 09:00 and ends on 6.8 at 10:00. Forward fill would report 3.5 for all four of those rows, and a check on the carried values alone would never have flagged them.

## Sample data

Two sensors in a fictional cold-storage warehouse, polled hourly from midnight to 11:00 on September 9, 2026, twenty-four rows in all. The freezer misses one reading on its own, then a run of three, then a run of two. The cooler reports nothing for its first two polls, then goes dark for six hours after 03:00 and comes back warm. Readings are held as integer tenths of a degree in a column named `tenths`, so no comparison against a limit depends on float rounding, and the file is deliberately not in time order, since every query sorts for itself.

## Known limits

- Two hours is a constant in two SQL files. A real cap belongs on the sensor list, since a freezer drifts slower than a cooler and a sensor on a door drifts faster than both.
- Forward fill assumes the last reading still holds, which suits slow-moving values like temperature and misleads on anything that changes in steps or spikes. For those, a blank is the honest output and the cap should be zero.
- A reading carried into a gap says what the sensor last saw and nothing about what it would see now. The blind-spot check uses the next real reading as the only evidence available, which confirms a breach after the fact and cannot place when it began.
- The correlated fill in query 02 searches back from each row only as far as the nearest real reading, so a sensor that stays dark for thousands of polls makes it slow in proportion to the square of that run's length. It is kept as the reference the one-pass version is checked against, and query 03 is the one to fill with.
- Timestamps carry no time zone, the queries sort them as text, and queries 03 through 05 subtract them as plain clock times, so stamps should be UTC or a fixed offset. Across a local fall-back, an hourly log repeats a stamp and the loader refuses it, while an unevenly polled one loads, sorts the repeated hour out of true order, and can make a carried reading look an hour younger than it is, which errs on the unsafe side.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
