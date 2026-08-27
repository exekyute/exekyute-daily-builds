# Cohort Retention Queries

Five SQLite queries that turn a bare activity log into a weekly cohort retention grid: users grouped by the week they first showed up, then a matrix of how many came back one, two, and three weeks later. The grid keeps two things apart that careless versions blur: a 0.0% cell means the week happened and nobody returned, a blank cell means the week has not happened for that cohort yet. The sample data puts both in the same column.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-weekly-activity.sql` | Activity rolled up to Monday-start weeks: active users and rows per week. |
| `sql/02-cohorts.sql` | Each cohort's week, size, and join-date range. |
| `sql/03-user-week-offsets.sql` | The long shape: one row per user per active week, as weeks since their cohort week. |
| `sql/04-retention-counts.sql` | Every observable cohort-by-offset cell with its count and percent, zeros included. |
| `sql/05-retention-grid.sql` | The pivot: one row per cohort, one column per week offset. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/cohort-retention-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against hand-counted answers:

```
python run.py --test
```

Ten checks cover the weekly rollup, the cohort sizes, the Sunday-boundary joiner, the collapsed same-week pair, the real zero, the unobservable cells, and the full grid, then print `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --activity data/invalid-activity.csv
```

It stops on the first problem and names the row: `invalid-activity.csv row 3: second activity for ana on 2026-07-06`. The row after that has a date without zero padding, which the loader would catch next.

## How the weeks work

Weeks run Monday to Sunday. `DATE(d, 'weekday 0', '-6 days')` advances any date to the Sunday that ends its week, then steps back six days to the Monday that started it. The boundary matters: cai's first activity is Sunday, July 12, and she lands in the cohort that started Monday, July 6, not the week about to begin. A user's cohort is the week of their first activity, and every later active week becomes a whole-week offset from it, so eva showing up twice in one week is still one retained cell.

## The zero and the blank

The first cohort's week 2 reads 0.0%: all three members skipped that week, and two of them came back in week 3, because retention is not obliged to fall smoothly. The youngest cohort's week 2 is blank: that week starts after the last activity in the log, so there is nothing to know yet.

Making that distinction takes two steps. A recursive spine crossed with the cohorts builds every cell whose week has started inside the data window, and a LEFT JOIN fills each one, so an empty week becomes a counted zero instead of a missing row. Cells outside the window are never generated, so the pivot leaves them NULL and the grid shows them blank.

## Sample data

Eight fictional users and 19 activity rows from July 6 to August 1, 2026, forming three Monday cohorts of 3, 3, and 2 users. Two users join on Sundays to work the week boundary, one user is active twice in the same week, and the first cohort's members collectively skip week 2. The grid comes out 100.0/66.7/0.0/66.7, 100.0/66.7/66.7, and 100.0/50.0 percent.

## Known limits

- The pivot writes columns `week_0` through `week_3` by hand. A longer window needs more `MAX(CASE)` lines, while the long form in `04` adapts on its own.
- Retained means any activity inside the calendar week. A rolling seven-day window from each user's join date is a different, equally defensible definition with different numbers.
- A user's cohort is fixed by their first activity ever, so someone returning after a long absence still counts in their original cohort rather than starting a new one.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
