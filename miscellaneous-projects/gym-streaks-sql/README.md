# Gym Streak Queries

Find out, from a log of timestamped check-ins, who is on a gym streak and who has lapsed as of a given day. Streak detection is the gaps-and-islands pattern: subtract each visit day's row number from the date itself, and consecutive days collapse onto one shared key that a plain GROUP BY collects. Mara Voss has the longest run in the sample at 14 days, and she and Aiko Tanaka are the only 2 of 7 members still on a streak on the report date.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-attendance-days.sql` | Days visited plus first and last visit per member. Timestamps collapse to distinct calendar days, so a morning and an evening session count as one visit. |
| `sql/02-streak-islands.sql` | Every consecutive-day streak per member, with start, end, and length. |
| `sql/03-longest-streaks.sql` | Each member's longest streak. Ties go to the earlier one. |
| `sql/04-current-streaks.sql` | Streaks still alive on the report date. |
| `sql/05-lapsed-members.sql` | Everyone with no visit in 14 or more days, including members who joined and never checked in once. |

## Running it

Python 3 and its standard library are all it needs. `run.py` loads the CSVs into an in-memory SQLite database, so there is no database server to set up.

```
cd miscellaneous-projects/gym-streaks-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against hand-counted answers:

```
python run.py --test
```

A passing suite prints `all checks passed` after nine checks: three counts (49 check-in rows, 48 member-days, 15 streaks), Mara's two streaks, Dev's duplicate check-in counting as one day, the longest and current streaks, the lapsed list, and two check-ins dated after the report date that must leave both as-of reports as they were.

The loader validates both CSVs before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --checkins data/invalid-checkins.csv
```

The first refusal ends the run with exit code 2, and the message names the file and the row: `invalid-checkins.csv row 3: member_id 99 has no row in members.csv`.

## How the streak detection works

Three steps, all in `sql/02-streak-islands.sql`.

1. Collapse timestamps to distinct member-days.
2. Number each member's days in date order with `ROW_NUMBER()`.
3. Subtract the row number from the day. Consecutive days all land on the same key; any skipped day makes the key jump.

Dev's first four visit days from the sample data show the trick:

| day | row number | day minus row number |
| --- | --- | --- |
| 2026-07-05 | 1 | 2026-07-04 |
| 2026-07-06 | 2 | 2026-07-04 |
| 2026-07-19 | 3 | 2026-07-16 |
| 2026-08-10 | 4 | 2026-08-06 |

The two consecutive July days share a key, and each gap after that pushes the key somewhere new. Group by that last column and each group is one streak. Nothing in the three steps is specific to a gym: any table with a key and a calendar date on each row finds its runs the same way.

## Sample data

Seven fictional members and 49 check-in rows across 48 distinct visit days, June 22 to August 19, 2026. I placed the rows by hand so every edge case shows up in the output: a 14-day streak, a broken streak, a duplicate same-day check-in, a weekends-only member whose streaks are all one day long, two lapsed members, and one member who joined and never visited.

The report queries pin the as-of date to 2026-08-19 so the sample gives the same answer every run. Against live data, swap the `params` CTE to `DATE('now')`. Check-ins dated after the as-of day are left out of the current-streak and lapsed reports, so those two answer for the report date even when the file runs past it.

## Known limits

- Streaks are calendar-day based. A check-in at 23:59 and another at 00:01 count as two separate days, and the timestamps carry no timezone.
- The 14-day lapsed threshold and the as-of date are constants inside the SQL files, not flags on the runner.
- Window functions need SQLite 3.25 or newer. Every current Python build includes it.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
