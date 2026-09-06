# Drawdown Queries

Five SQLite queries that score a daily portfolio series against its own running peak: how far below the high-water mark each day sits, every underwater stretch with its trough and recovery date, the maximum drawdown with its full anatomy, and a statement line for today. The sample series finishes 27.40 percent up and still spent 25 of its 40 days underwater, which is the point of the build: endpoints measure the trip, drawdown measures what it felt like to be on it.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-series-shape.sql` | The series at a glance, ending on the at-peak versus underwater split. |
| `sql/02-running-peak.sql` | Every day beside its running peak, drawdown percent, and status. |
| `sql/03-underwater-stretches.sql` | Each underwater stretch as one row: trough, depth, length, recovery date. |
| `sql/04-max-drawdown.sql` | The worst gap in the series: how high, how far down, how long down, how long back. |
| `sql/05-current-status.sql` | Where the series stands today against its high-water mark. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/drawdown-sql
python run.py
```

That prints all five reports against the sample series. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Ten checks cover the equality boundary from both sides, all four stretches, the max drawdown anatomy, and the status line, then print `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --values data/invalid-portfolio.csv
```

It stops on the first problem and names the row: `invalid-portfolio.csv row 4: dates must be consecutive; expected 2026-07-03`. The gap check exists because underwater durations count days: with missing dates, an eleven-day stretch quietly stops meaning eleven days, so the loader refuses gaps outright.

## The running peak

A cumulative MAX window, `MAX(value_cents) OVER (ORDER BY value_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`, gives each day the highest value the series has ever reached, and drawdown is the percent gap between the day and that peak; query 02 factors the frame into a named WINDOW clause. The comparison runs on exact integer cents and the boundary is strict: a day equal to its running peak counts as at the peak rather than underwater. That one choice does double duty, since it is also what lets a later re-touch of an old peak end a drawdown. The sample exercises both sides: July 8 sits flat at 11,400.00 and reads at peak, and July 22 climbs back to exactly the 12,000.00 peak and closes the eleven-day stretch.

## Underwater stretches

Query 03 is the flag-then-running-sum island trick from earlier builds, applied to the underwater flag. One fact makes the per-stretch arithmetic almost free: while the series is underwater the running peak cannot move, so within a stretch the peak is a constant, the trough is simply the minimum value, and the depth is one division. A stretch that ends before the data does was ended by a recovery, so its recovery date is just the next calendar day; the final stretch is still open and reports `not yet`.

## The max drawdown

Query 04 anatomizes the worst gap: the 12,000.00 peak first reached July 9, the 10,200.00 trough six days later, 15.00 percent down, and the first day back at or above the old peak seven days after that. A tie at the worst depth breaks to the earliest day, so the answer is deterministic. The peak date deliberately means first reached, since the sample sits at 12,000.00 twice before the slide begins. A series that never dipped reports `never underwater` rather than passing off the next ordinary day as a recovery event.

## Sample data

Forty consecutive days, July 1 to August 9, 2026, of a fictional portfolio's daily closing value, engineered so every drawdown lands on a whole or half percent: a one-day 1.00 percent dip, the 15.00 percent slide and full recovery, a 5.00 percent dip ended by a jump to a new high, and a 7.00 percent stretch that has climbed back to 2.00 percent below peak without recovering by the last row. Values are held as integer cents; the only rounding is at the displayed percentages.

## Known limits

- Drawdown measures path, not performance. This series would look excellent on an endpoints-only report and still handed its holder eleven straight underwater days; the reverse deception also exists, and neither number replaces the other.
- Daily closes only. An intraday trough between two closes is invisible, so true maximum drawdown can be worse than any daily series shows.
- Calendar days, not trading days. The loader demands one row per day, which fits a valuation series; a market series with weekend gaps wants one row per trading day and durations read as trading days, with the consecutive-date guard adjusted to that calendar.
- One series per file. Several portfolios mean PARTITION BY on the running MAX and the island numbering restarting per portfolio.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
