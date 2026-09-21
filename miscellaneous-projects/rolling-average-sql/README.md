# Rolling Average Queries

Five SQLite queries that work out a rolling seven-day average of a shop's daily sales, where a day the shop was shut or a day lost from the export simply has no row. A RANGE frame ordered by a whole day number keeps each window to seven calendar days however many rows fall in it, and the average is then read two ways: with a missing day as zero sales, or as unknown. The tempting ROWS frame averages the last seven rows instead, which on the sample span as many as 13 calendar days and put New Year's Day at 1333.94, where the days logged in its own week average 728.52.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-log-shape.sql` | The log at a glance: first and last day, calendar days between them, days logged and missing, missing Mondays apart from the rest, the longest gap and total sales. |
| `sql/02-rows-frame.sql` | The seven-day average over the last seven rows, with the earliest day each window reached and how many calendar days that spans. |
| `sql/03-range-frame.sql` | The seven-day average over seven calendar days, with how many of them are logged and what they sold. |
| `sql/04-rows-against-range.sql` | The two frames side by side, grouped by how many calendar days the ROWS frame spans, with the day each group drifts most. |
| `sql/05-zero-or-unknown.sql` | Every day's seven-day average read with missing days as zero and as unknown, the first six days flagged as partial windows. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.28 or newer, the first release whose RANGE frames take a number before PRECEDING.

```
cd miscellaneous-projects/rolling-average-sql
python run.py
```

That prints all five reports against the sample log. The test run checks the queries and the loader against hand-computed answers:

```
python run.py --test
```

Eighteen checks run. Six on the sample cover the log's shape, every day of the ROWS frame, the RANGE frame and the zero-or-unknown reading, and the two frames grouped by span. The sixth prints all five reports and checks their column names, a rule as wide as each column, how many rows each prints and the first of them, that a query file that fails, has no query result, is not UTF-8 or is gone by the time it is read, or a folder named like one, stops them with a one-line message, and that a value the printer is handed as nothing comes out as a blank cell.

Five more run on logs built for the suite. The first is nine days in a row across a leap day, one logged at 0.00, on which both frames hold the same rows and a full window reads the same either way, and the same log without the 0.00 day, which moves only the unknown reading. The second spaces four days so that one sits exactly six days back from the next and one seven, and the ROWS frame reaches across 15 days; it runs beside the sample with the RANGE frame ordered by the date text. The rest cover two logs where two days in one span drift equally far, one each way, with the earlier day drifting down in one and up in the other; a log of a single Monday at the largest amount a day may hold, and a Sunday and a Monday; the sample stored in reverse in a table with no key; and every day from 1970-01-01 to 2200-12-31, and two days at its ends, which have to run inside the step budget beside a query that would run for ever.

Seven exercise the loader and the command line. They refuse the included bad log, which has an amount written with a thousands separator, and a day listed twice; days in the wrong shape, days that do not exist, such as 2025-02-29, and days before 1970 or after 2200, next to 1970-01-01, 2024-02-29 and 2200-12-31, which load; and amounts that are negative, zero-padded, in exponent form, with a comma, a dollar sign or a thousands separator, or in Arabic-Indic digits, next to 0.00 and 999999.99, which load.

They count rows past blank lines, name a stray quote by its own row, refuse rows with too many or too few fields, text after a closing quote, a quote left open, a field past the parser's limit and a bad or reordered header, and cut a long value short in the message. They refuse an empty file, one with only a header, one that is not UTF-8 from its first line or only far down, a folder, a read that gives way partway and a line past 1000000 characters, and cut off a line that never ends at that cap rather than read it whole. A log of every day the loader allows, 84371 rows, loads, and one row more, which can only repeat a day, is stopped as it is read.

On the command line they refuse a missing file, a name with a wildcard in it and a test run on any file other than the sample, and check that output and messages go out as UTF-8. The run ends with `all checks passed`.

The loader validates the log before any query runs. Point it at the included bad log to see a rejection:

```
python run.py --sales data/invalid-sales.csv
```

It stops at the first problem it reaches, naming the row where it has one. A byte that is not UTF-8 is the exception: the file is decoded about 8 KB at a time, so a bad byte is reported first, without a row, when a problem sits a little above it in the same stretch of the file. On the included bad log:

```
invalid-sales.csv row 46: sales '1,062.85' is not an amount from 0.00 to 999999.99 written like 412.50
```

## Where the ROWS frame goes wrong

Query 02 averages each day with the six rows before it, `ROWS BETWEEN 6 PRECEDING AND CURRENT ROW`. ROWS counts rows, not days. The shop shuts every Monday, and any seven days in a row hold a Monday, so after the first week every window spans at least 8 calendar days, counting the day itself. Around each day missing from the export it spans 9 or 10, and across the Christmas closure, five days with nothing from 25 to 29 December, it spans 13.

On New Year's Day the seven rows run back to 20 December and take in the Christmas rush from the 20th to the 24th, which holds the three busiest days of the log. They average 1333.94. The three days logged in the week that ends on New Year's Day average 728.52, and none of them sold more than 1062.85.

Query 04 groups the days by how many calendar days the ROWS frame spans. The two frames agree on the first six days, which run six days in a row, so both frames hold every row so far; they differ on every one of the other 48. The drift runs both ways: at 8 days the widest is on Christmas Eve, where ROWS adds the quiet 17th to the six days of that week and reads 118.32 low, and at 13 days it is New Year's Day, 605.42 high.

## Seven calendar days

Query 03 orders the frame by a whole day number, `CAST(julianday(day) AS INTEGER)`, and uses `RANGE BETWEEN 6 PRECEDING AND CURRENT ROW`. RANGE takes every row whose day number lies within six of the current one, so the frame is the day and the six before it, whether they hold seven rows or one. julianday counts across month ends, year ends and leap days without any help.

Ordering the same frame by the date text looks as if it should work. It runs without an error, but SQLite cannot take six from text, so each day's frame holds only that day, and every row's seven-day average is its own sales. The suite checks this on the sample, and SQLite 3.31, 3.34 and 3.50 all behave the same way.

## Zero or unknown

Query 05 reads each window both ways. As zero, the average is the week's sales over seven; as unknown, it is the week's sales over the days logged. The log cannot choose between them for you: a day the shop was shut sold nothing, so zero is right for it, but a day lost from the export could have sold anything, and both show up as a missing row.

The gap is widest after Christmas. The window ending 30 December holds only Christmas Eve and the 30th, so it reads 450.36 as zero and 1576.28 as unknown, and there the shop really was shut, so zero is the honest figure per calendar day. In the week of the missing Saturday the zero reading runs from 487.69 to 495.49 against 682.77 to 693.69 as unknown, and there zero is the wrong one: the bakery was open that Saturday, and Saturday is its busiest day.

A day logged at 0.00 is a known zero and counts in both readings. Read as zero, a missing day and a day logged at 0.00 give the same average, which is exactly the difference the unknown reading keeps. The first six days of the log have windows that start before it began, which neither reading can fill, so query 05 flags them as partial.

## Rounding

Every average is worked out in whole cents and rounded half up in whole numbers, `(2 * sum + days) / (2 * days)`. Eleven of the averages in query 03 land on an exact half cent. Four of them, 736.175, 743.775, 782.525 and 898.525, sit just under the half as a float of dollars, so printf or ROUND on the float prints them a cent low on SQLite 3.50 and right on 3.31 and 3.34.

Read as zero, no average can land on a half. Seven is odd.

## Sample data

54 days of sales at a fictional bakery from Tuesday 4 November 2025 to Sunday 11 January 2026, in `sales.csv`, sorted by day and written in dollars and cents. Of the 69 calendar days, 15 have no row: the nine Mondays the bakery shuts, 25 to 28 December for Christmas, and two days missing from the export, Saturday 22 November and Thursday 8 January. Sales climb through December to 2418.35 on Christmas Eve and total 45147.60.

## Known limits

- A log holds one row per day from 1970-01-01 to 2200-12-31, so at most 84371 rows, and each day's sales run from 0.00 to 999999.99. A day's sales cannot be negative, so a day of refunds larger than its takings cannot be logged. A line of the file holds at most 1000000 characters, and a field at most 131072, the CSV parser's limit.
- The log says nothing about why a day is missing, so query 05 prints both readings rather than one. A table of the days the shop was shut would let a query read those as zero and every other gap as unknown.
- Only logged days get a row in the reports. A closed Monday has no seven-day average of its own; that would need a calendar of every day joined to the log.
- The window is seven days, written into queries 02 to 05: the 6 in every frame, the six days back in query 03's window_from, the 7 and 14 in query 05's zero reading and the 6 in its partial flag. Changing it means changing each copy.
- Partial windows at the start are flagged, not dropped or scaled, so their zero reading counts every day before the log as a day of no sales.
- A query that runs past two hundred million SQLite steps is stopped with an error. A log of every day the limits allow takes about a tenth of that, on 3.31 and 3.34 as much as on 3.50, though those older versions work a named CTE out again at every mention, which is why each query names its dearest step once.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
