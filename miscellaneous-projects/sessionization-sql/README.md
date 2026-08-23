# Sessionization Queries

Five SQLite queries that cut a raw page-view log into visitor sessions using a 30-minute timeout, then report on them: numbered sessions, entry and exit pages, per-visitor rollups, and a one-row site summary with the bounce rate. `LAG` measures the gap back to each visitor's previous view, a gap of 30 minutes or more raises a new-session flag, and a running `SUM` over those flags hands out the session numbers. Gaps are compared in whole seconds via `strftime('%s')`, because `julianday()` differences are floats and a gap of exactly 30 minutes could land a hair under the threshold.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-view-gaps.sql` | Every view with the seconds since that visitor's previous view and the new-session flag. |
| `sql/02-session-ids.sql` | The same views with a session number per visitor, from a running sum over the flags. |
| `sql/03-session-summary.sql` | One row per session: start, end, minutes, pages, entry page, exit page. |
| `sql/04-visitor-rollup.sql` | Per visitor: sessions, views, bounces, pages per session, total minutes. |
| `sql/05-site-metrics.sql` | The whole site in one row, including the bounce rate. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/sessionization-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against hand-counted answers:

```
python run.py --test
```

Ten checks cover the row counts, the gap seconds around the 30-minute line, the session counts per visitor, the midnight-crossing session, the entry and exit pages, the bounces, and the site summary row, then print `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --pageviews data/invalid-pageviews.csv
```

It stops on the first problem and names the row: `invalid-pageviews.csv row 3: view_ts '2026-08-05 9:15:00' is not YYYY-MM-DD HH:MM:SS`. The row after that has a page with no leading slash, which the loader would catch next.

## How the numbering works

Two moves, both in `sql/02-session-ids.sql`. First, flag the views that start a session: a visitor's first view, or any view 1800 seconds or more after their previous one. Second, take a running sum of the flags per visitor in time order. Every flagged view bumps the sum by one, every other view inherits it, and the sum is the session number.

Ben's four rows show the whole thing, including both sides of the threshold:

| view_ts | gap_seconds | starts_session | session_number |
| --- | --- | --- | --- |
| 2026-08-05 13:00:00 | | 1 | 1 |
| 2026-08-05 13:29:59 | 1799 | 0 | 1 |
| 2026-08-05 14:00:00 | 1801 | 1 | 2 |
| 2026-08-05 14:30:00 | 1800 | 1 | 3 |

One second decides his first session: 1799 keeps the pricing view inside it, and the exactly-1800 gap later that day starts a fresh one.

## Traps the sample data sets

- Dee's first session runs from 23:45 to 00:10 the next day. Grouping views by calendar date would cut it in half; the gap rule keeps it whole.
- Eva's three rows are shuffled in the CSV. The window's `ORDER BY view_ts` does the sorting, so nothing depends on file order.
- Cai visits once and leaves. One-view sessions are the bounces, counted with `SUM(pages = 1)`, which works because the comparison is 1 when true and 0 when not.
- `LAST_VALUE` in the session summary needs its frame spelled out as `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`. The default frame stops at the current row, which would quietly make every row its own exit page.

## Sample data

Five fictional visitors and 17 page views across August 5 and 6, 2026, which sessionize into 9 sessions. Four are bounces, a 44.4% bounce rate. The average session has 1.89 pages and the mean session length is 10.89 minutes. The longest session is Ben's first, at 29.98 minutes across two views, one second short of the timeout.

## Known limits

- The 30-minute timeout is a constant inside each SQL file, not a runner flag. Change 1800 in one place per file.
- Two views by the same visitor in the same second are rejected at load, because the windows order by timestamp alone and ties would make the session numbering depend on unspecified row order.
- Session length is last view minus first view, so a one-view session is 0 minutes no matter how long the person actually read the page.
- Timestamps carry no timezone. A visitor browsing across a clock change would get a wrong gap, and the data has to arrive in one consistent zone.
- The site summary averages per-session minutes that were already rounded to 2 decimals, so it can drift a hundredth from the unrounded mean.
- Window functions need SQLite 3.25 or newer. The SQLite bundled with the official Python installers covers it; a Linux Python that links an old system libsqlite3 may not.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
