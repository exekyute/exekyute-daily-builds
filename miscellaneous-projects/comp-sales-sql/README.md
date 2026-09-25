# Comparable Sales Queries

Five SQLite queries that compare a store chain's daily sales with the same days a year earlier and report comparable-store growth week by week. Each day is set against the day 364 days before it, the same weekday 52 weeks back, and a store counts only on a day it traded both then and now, so a new store or one shut for a renovation drops out for exactly the days that cannot be matched. The obvious comparison, the same date a year earlier with every store counted, puts the sample's eight weeks at +15.7 percent against a comparable +2.2.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-log-shape.sql` | The log at a glance, store by store: its first and last day, the days it traded, and the days it was shut between them. |
| `sql/02-same-date-naive.sql` | Each day of the report weeks against the same date a year earlier, every store counted, gathered by weekday, with the weekday each one was set against. |
| `sql/03-comp-stores.sql` | Comparable-store sales store by store: days open now and 52 weeks earlier, the days that count, and growth on them. |
| `sql/04-weekly-comp.sql` | Each week against the same week 52 weeks earlier, for every store and for comparable stores only, with a total line. |
| `sql/05-weekday-three-ways.sql` | Growth by weekday three ways: same date with every store, same weekday with every store, and same weekday with comparable stores. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.8.3 or newer for recursive CTEs and printf. The queries give the same rows on SQLite 3.31.1, 3.34.0 and 3.50.4.

```
cd miscellaneous-projects/comp-sales-sql
python run.py
```

That prints all five reports against the sample log. The test run checks the queries and the loader against hand-computed answers:

```
python run.py --test
```

Twenty checks run. Seven use the sample: one for each report, and one that prints all five and checks their column names, a rule as wide as each column, how many rows each prints and the first and last of them, with the blank that query 02 leaves in its total line printing as a blank cell. That check also makes sure a query file that fails, has no query result, is not UTF-8 or is gone by the time it is read, or a folder named like one, stops the reports with a one-line message. The seventh stores the sample newest first in a table with no key and gets the same five reports.

Six more run on logs built for the suite. On a log with a leap day in its report weeks, the same date a year earlier is 366 days back once the leap day is past, and 29 February and 1 March both land on 1 March, while the same weekday 52 weeks back reads 0.0 on a store that sold the same each weekday. A log with a store shut now has to take the matching days 52 weeks earlier out of comparable sales, count a store that opened during the earlier weeks from 52 weeks after its first day, and leave out a part week at its end.

A log that starts on a Sunday has to report from exactly 52 weeks later, print a week with no sales in either year, and leave growth blank where the year before sold nothing. A log whose only report week has no row in either year still prints every total line, and a table too short for any report week gives no report rows. On another log every growth figure lands on an exact half, with one above zero and one below in each column of queries 02, 04 and 05.

One check makes sure the totals each query works out on its own agree, on the sample and on the leap-day, shut-store, Sunday-start, empty-week and exact-half logs. The sixth runs every query over a log of 100000 rows spanning 1970-01-01 to 2200-12-31, 99998 of them from different stores on one day, inside the step budget, beside a query that would run for ever, which the budget stops.

Seven exercise the loader and the command line. They refuse the included bad log, which has 29 February 2025 in it, and a store listed twice on one day; days that are not on the calendar, written in another form, with a time or in fullwidth digits, before 1970 or after 2200, or blank, next to 1970-01-01, 2200-12-31 and 2024-02-29, which load; store codes in lower case, with a space, a doubled or outer hyphen, an accent or fullwidth letters, too long or blank; and amounts that are negative, whole, with one or three decimal places, zero-padded, of seven digits, in exponent form, blank, with a comma, a dollar sign or no digit before the point, or with Arabic-Indic digits in them, next to 0.00 and 999999.99, which load.

They count rows past blank lines and a line of spaces, name a stray quote by its own row, in a data row or in the header, refuse rows with too many or too few fields, a line of commas, a tab, text after a closing quote, a quote left open, a field past the parser's limit and a bad, renamed or reordered header, also one found after blank lines, written as a single quoted field or with a trailing comma, and cut a long value or header short in the message.

They refuse an empty file, one of blank lines, one with only a header, one that is not UTF-8 from its first line or only far down, or holds only part of a byte-order mark, a folder, a read that gives way partway and a line past 1000000 characters, while a byte-order mark, blank lines before the header, spaces around unquoted fields and a line holding one empty quoted field load. They refuse a log too short for a report week, at 370 days from a Sunday and 376 from a Monday, next to 371 and 377, which load, stop a log past 100000 rows as it is read, before a bad byte further down, and load one of exactly 100000. On the command line they refuse a missing file, a name with a wildcard in it and a test run on any file other than the sample, and check that output and messages go out as UTF-8. The run ends with `all checks passed`.

The loader validates the log before any query runs. Point it at the included bad log to see a rejection:

```
python run.py --sales data/invalid-sales.csv
```

It stops at the first problem it meets and names the row where it has one. The file is decoded in blocks, so a byte that is not UTF-8 can be met a few kilobytes ahead of the row being checked:

```
invalid-sales.csv row 405: sale_date '2025-02-29' is not a calendar date written like 2025-12-07, from 1970-01-01 to 2200-12-31
```

## Where the same date goes wrong

Query 02 sets each day against `date(day, '-1 year')`, the same date a year earlier. That date is 365 days back, or 366 across a leap day, so it is never the same weekday. The report's eight Saturdays each meet a Friday and together read +50.2 percent, its Fridays meet Thursdays and read +61.0, and its Sundays meet Saturdays and read -35.1. Set against the same weekday, with every store still counted, the same days read between +8.0 and +31.5.

Across a leap day the same function sends both 29 February and 1 March to 1 March of the year before, so one day of last year's sales counts twice. The sample has no leap day in its report weeks; the leap-day log in the suite shows it.

Counting every store is the second error. CLAYTON-PARK opened on 21 December 2024 and BEDFORD was shut for a renovation from 8 to 28 January 2025, so for part of the report weeks each has sales now and nothing a year earlier. With them in, the eight weeks read +15.7 percent. Comparable stores grew 2.2.

## Comparable stores

Query 03 sets each day against the day 364 days earlier, which is always the same weekday. A store counts on a day only when it has a row on both days, and that one rule covers the new store and the renovation alike. CLAYTON-PARK counts from 20 December 2025, 52 weeks after its first day, on 43 of the 56 report days. BEDFORD's 21 days from 7 to 27 January 2026 have no day 52 weeks earlier and stay out, and its other 35 count.

The rule works the other way too. A store shut now takes the days 52 weeks earlier out of comparable sales, since there is nothing to set them against, while the all-store figures still count them as last year's sales. SQLite before 3.39 has no FULL OUTER JOIN, so queries 03 and 04 gather every store-day open on either side with a LEFT JOIN one way and a NOT EXISTS the other.

## Week by week

Query 04 rolls the days up into weeks that run Sunday to Saturday, keyed by the date of each week's Sunday, `date(day, '-6 days', 'weekday 0')`. The week from 28 December to 3 January stays one week, where `strftime('%Y-%W')` would give its seven days three keys: 2025-51, 2025-52 and 2026-00. The ISO week from `strftime('%G-%V')` runs Monday to Sunday and would still split it in two, and 3.31 and 3.34 return NULL for `%G`, `%V` and `%u` without an error.

All-store growth reads +19.8 and +13.0 in the first two weeks, when 13 of CLAYTON-PARK's days have nothing a year earlier to set against. Over Christmas and New Year, when every store counts, it matches the comparable figure at +4.4 and +3.1, then climbs to +34.1 in mid-January against the weeks BEDFORD was shut. Comparable growth stays between -0.2 and +4.4 throughout.

A week is reported only when all seven of its days, and the same seven 52 weeks earlier, are inside the log. So the report starts on the first Sunday at least 364 days after the log's first day and ends on the last Saturday on or before its last day, and the loader refuses a log too short for even one such week.

## Rounding

Growth is worked out in whole numbers and rounded half away from zero to a tenth of a percent. Six figures in the sample land exactly on a half: comparable growth of 2.05 and -0.15 percent in the first two weeks, all-store growth of 21.15 in the week of 4 January, -2.05 for NORTH-END, 2.15 for comparable stores overall, and 50.15 for Saturdays in query 02. Held as floats, all six sit just under the half: SQLite 3.50's printf gives 2.0, -0.1, 21.1, -2.0, 2.1 and 50.1, while 3.31 and 3.34 give 2.1, -0.2, 21.2, -2.1, 2.2 and 50.2, as the queries do on every version.

## By weekday

Query 05 sets the three comparisons side by side. Against the same date with every store counted, Sundays read -35.1 and Fridays +61.0. Against the same weekday, the all-store figures run from +8.0 to +31.5 and the comparable ones from -6.1 to +16.2.

Wednesday and Thursday still stand out, and the weekday is not why. Christmas Day and New Year's Day fell on Wednesdays in the 2024-25 season and on Thursdays in 2025-26, so the report's Wednesdays hold Christmas Eve and New Year's Eve against the two holidays 52 weeks earlier, and its Thursdays hold the holidays against Boxing Day and an ordinary Thursday. Leave out those two Wednesdays and two Thursdays, and comparable growth on both weekdays falls under 1 percent.

No single offset matches both. The same date keeps Christmas against Christmas; the same weekday keeps Saturday against Saturday. Over whole weeks the sample's holidays and their eves fall in the same report week in both years, so each week in query 04 has them on both sides.

## Sample data

Five fictional corner stores in one chain, with one row for each day a store traded, from Monday 2 December 2024 to Saturday 31 January 2026: 2090 rows in `sales.csv`, listed by day and store. Every store trades every day, holidays included, except that CLAYTON-PARK opened on Saturday 21 December 2024 and BEDFORD was shut from Wednesday 8 to Tuesday 28 January 2025 for a renovation. The report weeks run from Sunday 7 December 2025 to Saturday 31 January 2026, and in both seasons the chain sells less on Christmas Day and New Year's Day than on the days either side.

## Known limits

- A holiday on a fixed date lands on a different weekday each year, and the same weekday 52 weeks earlier then sets it against an ordinary day, as query 05 shows. When this year's holiday falls on a Sunday, or on a Monday with a 29 February since last year's, last year's holiday is set against the week before, and the weekly figures move as well.
- Fifty-two weeks is 364 days, a day short of a year and two short across a leap day, so the comparison creeps a day earlier through the calendar each year. Retail calendars catch up with a 53rd week every five or six years; these queries have no such week.
- A store enters comparable sales exactly 52 weeks after its first day, and a renovated store stays in on the days it traded in both years. Some chains wait 13 months, or take a remodelled store out for the whole period; either would be one more condition on the pairs.
- A row means the store traded that day, 0.00 included, and a day with no row is a day shut. A day missing from an export reads as shut, and it and the day 52 weeks away from it drop out of comparable sales.
- Queries 02 and 05 read the same date a year earlier as no sales when it falls before the log. That happens in the first report week when the log starts on a Sunday, where it costs that week's Sunday and, across a 29 February, its Monday too, and when the log starts on a Saturday with a 29 February in the year between, where it costs the Sunday.
- Days run from 1970-01-01 to 2200-12-31, amounts from 0.00 to 999999.99, and a log holds at most 100000 rows. A line of the file holds at most 1000000 characters, and a field at most 131072, the CSV parser's limit.
- A query that runs past 200000 thousand SQLite steps is stopped with an error. The costliest log tried within the limits, 99998 stores trading on one day in a log that spans every date allowed, takes under a fifth of that, on 3.31 and 3.34 as on 3.50, though those older versions work a named CTE out again at every mention, which is why each query names its costliest step once.
- The report-week rule, the 364-day offset and the growth rounding are written out in every query that uses them, so each file runs on its own, and the loader repeats the report-week rule. A change to any of them has to be made in each copy.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
