# Weekday Pivot Queries

The queries turn a café's one-row-per-day sales log into a week-by-weekday grid, total it both ways, and average each weekday twice: over the days the café opened, and with closed days counted as zero. With no `PIVOT` in SQLite, each column is a `SUM` over a `CASE` with no `ELSE`, which leaves a closed day blank and keeps the one day the café opened and sold nothing at 0.00. Query 02 reads strftime's 0 as Monday and fills with `ELSE 0`: the first makes Sunday, a day the café is usually closed, look like its busiest day, and the second prints every closed day as 0.00.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-sales-shape.sql` | The log at a glance: days trading, weeks, the day that sold nothing, the total. |
| `sql/02-naive-pivot.sql` | A first-attempt pivot, shifted one day and zero-filled. |
| `sql/03-pivot.sql` | The grid done right, Monday first, with closed days left blank. |
| `sql/04-totals.sql` | The grid with a total for each week and a row totalling each weekday. |
| `sql/05-weekday-averages.sql` | Each weekday's average over the days it opened, and with closures counted as zero. |

## Surprises in strftime, ORDER BY and printf

`strftime('%w')` returns its day number as text, Sunday as `'0'`, and the text `'0'` is not equal to the integer 0. Written with `= 0`, query 02's first column reads 0.00 in all four weeks, the 540.00 taken on Sunday, August 16 included. Queries 03 to 05 cast to INTEGER before the `(w + 6) % 7` remap to Monday-first. `strftime('%u')` would give Monday as 1 directly in SQLite 3.50, but it returns NULL on 3.34.0 and 3.31.1, where the remap still works.

```sql
SELECT strftime('%w', '2026-08-30') = '0', strftime('%w', '2026-08-30') = 0;
-- 1 | 0
```

A name in `ORDER BY` resolves to an output column before an input column of the same name. Query 05 outputs its label as `day` for that reason. Aliased as `weekday`, its rows sort alphabetically, Friday first, and a test checks the order.

```sql
WITH t(weekday, label) AS (VALUES (0, 'Mon'), (1, 'Tue'), (4, 'Fri'))
SELECT label AS weekday FROM t ORDER BY weekday;
-- Fri, Mon, Tue
```

`printf()` rounds the double it is handed, and the double nearest 822.915 sits just below it. Query 05 rounds each average to whole cents with `ROUND()` before formatting, and a test log built to average exactly 822.915 checks for 822.92. SQLite 3.34.0 and 3.31.1 print 822.92 for both expressions, so without the `ROUND()` the last digit would depend on the release.

```sql
SELECT printf('%.2f', 82291.5 / 100.0), printf('%.2f', ROUND(82291.5) / 100.0);
-- 822.91 | 822.92
```

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.8.3 or newer for common table expressions.

```
cd miscellaneous-projects/weekday-pivot-sql
python run.py
```

That prints all five reports against the sample log. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Sixteen checks cover the shifted columns in query 02's grid, the blank and zero cells, both margins of the totals, the two averages, and the order the weekdays print in, plus three logs built to catch edge weeks, a week closed throughout, and an average landing on half a cent, then print `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --sales data/invalid-sales.csv
```

It stops on the first problem and names the row: `invalid-sales.csv row 4: sale_date 2026-08-04 appears twice; the log holds one row per trading day`. Two rows for one date would land in the same cell of the grid and be added together, so each date is allowed once.

## The naive pivot

A pivot turns rows into columns: one `SUM(CASE WHEN weekday = ... THEN cents END)` per day of the week, grouped by week. Query 02 gets two things wrong. `strftime('%w')` numbers the days from Sunday as 0, so treating 0 as Monday shifts every column one day: the column labelled `mon` holds Sunday and the one labelled `sun` holds Saturday. That grid puts 710.00, 690.00, 720.00, and 700.00 under Sunday, which is where Saturday's sales went.

The second mistake is `ELSE 0`. A week with no row for a weekday still gets 0.00 in that column, so every Sunday without a row reads as a day of zero sales, identical to a day the café opened and sold nothing. That includes Sunday, August 30, which falls after the last row in the log and was never recorded either way.

## The pivot done right

Query 03 fixes the shift by adding 6 and taking the remainder by 7, which turns Sunday-first 0 to 6 into Monday-first 0 to 6. It fixes the zero-fill by leaving out the `ELSE`: for a weekday with no row, every `CASE` is NULL and so is the `SUM`, while the storm day on August 19, open with no sales, contributes a real 0 and sums to 0. The grid prints a closed day blank and the storm day as 0.00. A blank means only that the log has no row for the day: inside the log's dates that is a closure, but the first and last weeks can hold days the log never reached, like that Sunday, August 30.

The blank has to be caught before formatting. `printf('%.2f', NULL)` returns `0.00` in SQLite rather than NULL, so a column formatted directly would bring the zero-fill straight back; each cell is a `CASE` that returns a blank first.

## Margins, and what zero-filling costs

Query 04 adds a total for each week and a final row totalling each weekday across all four weeks, stacked under the weekly rows with `UNION ALL`. Both margins sum the same sales, so the bottom-right cell has to equal the whole log, 11,730.00, which the test suite checks against query 01.

Query 05 crosses a calendar of every week with every weekday, keeps only the days between the first and last row in the log, and averages each weekday two ways. `AVG` skips the closed days and averages the days the café opened; `AVG(COALESCE(cents, 0))` counts each closed day as a day of zero sales. The two agree on the five weekdays the café never closed and part on the other two: Monday falls from 420.00 to 315.00 and Sunday from 540.00 to 180.00, because a zero-filled grid treats a day off as a bad day. Keeping only days inside the log is what stops Sunday, August 30 from counting as a fourth closed Sunday.

## Sample data

Twenty-four trading days at a fictional café, logged from Monday, August 3 to Saturday, August 29, 2026, across four Monday-start weeks. It opens Monday to Saturday, and of the three Sundays the log covers it closed two and opened one for an event. It closed one Monday for a staff day, and on Wednesday, August 19 it opened through a storm and sold nothing. The file is not in date order, which none of the queries need.

## Known limits

- Seven columns are written out by hand, once per weekday, in each pivot query. SQLite has no `PIVOT` and no way to generate columns from data, so a grid whose columns are not fixed in advance, such as one column per product, needs the SQL built by the calling code.
- Weeks start on Monday. A Sunday-first calendar changes the remap and the week start together, and changing only one of them shifts the grid by a day again.
- The grids in queries 03 and 04 have a row only for weeks holding at least one sale, since a week closed throughout gives them nothing to group. Queries 01 and 05 count such a week from a calendar of weeks, and a grid meant to show it as a blank row needs the same calendar joined in.
- The period a log covers is taken to run from its first row to its last. A café closed on the first or last days of the period it meant to report has no way to say so, since a closed day leaves no row; a declared start and end date would.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
