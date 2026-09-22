# Fiscal Year-to-Date Queries

Five SQLite queries that total a monthly revenue log year to date on a fiscal year running from April to March, the year the Nova Scotia and federal governments both budget on, and set each month's year-to-date against last year's to the same month. The fiscal year and fiscal month come from month arithmetic, a count of months shifted back by three, and a month missing from the log leaves its year's total blank rather than counting as zero. On the sample, calendar year-to-date at August 2026 reads 4 percent up on the year before, while fiscal year-to-date, April to August against April to August, is 2.5 percent down.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-log-shape.sql` | The log at a glance: its first and last month, the months it holds, how many are missing and how many are a real zero, the fiscal years it touches and how far into the last one it runs. |
| `sql/02-calendar-ytd.sql` | Year-to-date the calendar way: a running total that starts again each January, last year's total to the same calendar month, and the growth between them. |
| `sql/03-fiscal-ytd.sql` | Every month from the April that opens the first fiscal year, with its fiscal year, fiscal month, revenue and fiscal year-to-date, and the first month missing where a total cannot be known. |
| `sql/04-fiscal-growth.sql` | Each month's fiscal year-to-date against last fiscal year's to the same fiscal month, with the growth, and the calendar growth beside it. |
| `sql/05-year-summary.sql` | One line per fiscal year: the month it runs to, its months and missing months, revenue to date, the same months last year, the growth, and the whole of last year. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.25 or newer for window functions.

```
cd miscellaneous-projects/fiscal-ytd-sql
python run.py
```

That prints all five reports against the sample log. The test run checks the queries and the loader against hand-computed answers:

```
python run.py --test
```

Eighteen checks run. Six on the sample cover the log's shape, the calendar running totals and their growth, the fiscal running totals, fiscal growth month by month beside the calendar growth, and the year summary. The sixth prints all five reports and checks their column names, a rule as wide as each column, how many rows each prints and the first of them, that a missing month prints with blank cells, and that a query file that fails, has no query result, is not UTF-8 or is gone by the time it is read, or a folder named like one, stops them with a one-line message.

Six more run on logs built for the suite. The first checks that the reports agree with each other, on the sample and on every log the suite builds: query 04's calendar growth is query 02's, and query 05's revenue, last year's figure for the same months and growth are those of queries 03 and 04 at the month each year runs to. The second covers fiscal months across a change of calendar year, a log that starts in February, whose first fiscal year then has two months logged and ten missing, and one that starts in March, the names of fiscal years that cross a century and of 2200-01 with its leading zero, a log of one month in 2025-03, which belongs to 2024-25, and a log of one month in 1970-01, which reaches back to 1969-04. The third puts two gaps in one fiscal year and a whole fiscal year with no rows at all, and the fourth puts growth on exact halves, which have to round away from zero in every query that prints a growth figure, beside growth against a zero, which is blank, and a year that falls to nothing, which reads -100.

The fifth stores the sample in the opposite order in a table with no key and gets the same five reports. The sixth runs every month from 1970-01 to 2200-12 at the largest amount, and a log of just those two months, through each query inside the step budget, with twelve months at the largest amount printed to the cent, beside a query that would run for ever, which the step budget stops.

Six exercise the loader and the command line. They refuse the included bad log, which lists a month twice; load a log of every month the loader allows, 2772 of them, and refuse a row past them as it is read, before a byte that is not UTF-8 further down; refuse months past 12, at 00, without a leading zero or with a two-digit year, with a slash, a day, a month name, written as a fiscal year like 2025-26 or in fullwidth digits, blank, or outside 1970 to 2200; and refuse amounts that are negative, whole, with one or three decimal places, zero-padded, nine digits before the point, in exponent form, blank, with a comma, a dollar sign or a thousands separator, with no digit before the point, or with Arabic-Indic digits in them, next to 0.00, 0.01 and 99999999.99, which load.

They count rows past blank lines and a line of spaces, name a stray quote by its own row, in a data row or in the header, refuse rows with too many or too few fields, a line of one comma or of three, a tab, text after a closing quote, a quote left open, a field past the parser's limit and a bad, renamed or reordered header, also one written as a single quoted field or with a trailing comma, and cut a long value or header short in the message, while a value of exactly 40 characters shows whole. They refuse an empty file, one of blank lines, one with only a header, one that is not UTF-8 from its first line or only far down, or holds only part of a byte-order mark, a folder, a read that gives way partway, a line past 1000000 characters and a line that never ends, while a byte-order mark, blank lines before the header, spaces around unquoted fields and a line holding one empty quoted field load. On the command line they refuse a missing file, a name with a wildcard in it and a test run on any file other than the sample, and check that output and messages go out as UTF-8. The run ends with `all checks passed`.

The loader validates the log before any query runs. Point it at the included bad log to see a rejection:

```
python run.py --revenue data/invalid-revenue.csv
```

It stops at the first problem it reaches, naming the row where it has one. A byte that is not UTF-8 is the exception: the file is decoded about 8 KB at a time, so a bad byte is reported first, without a row, when a problem sits a little above it in the same stretch of the file. On the included bad log:

```
invalid-revenue.csv row 17: 2025-07 appears twice; one row per month, with the amounts added together
```

## Why calendar year-to-date falls short

Query 02 keeps a running total partitioned on the calendar year, so it starts again every January. On an April year that reset lands in the tenth month. At 2026-01 it reports one month, 143955.28, while the fiscal year 2025-26 is ten months old and stands at 3166874.77 in query 03. January to March always report one to three months of a year that is ten to twelve months in.

The comparison goes wrong with it. At 2026-08 the calendar total runs from January to August on both sides and reads 4 percent up, 2510553.30 against 2414247.11. But January to March 2026 are the last three months of 2025-26, and they came in 53 percent above the same quarter a year earlier. The months that belong to 2026-27, April to August, are 2.5 percent down on the same months of 2025-26, and query 04 prints that as -3.

The log opens in April 2024, the first month of a fiscal year, so calendar 2024 has no January to March at all. Every calendar comparison through 2025 sets a year counted from January against one counted from April: 2025-04 reads 189 percent up, four months against one.

## Fiscal year and fiscal month

Query 03 counts each month as the year times twelve plus the month counted from zero, and takes three off. Divided by twelve, that count gives the calendar year the fiscal year starts in; the remainder plus one is the fiscal month, 1 for April and 12 for March. 2025-01 is 24300 in months, 24297 after the shift, and 24297 is 2024 twelves with 9 left over: fiscal month 10 of 2024-25. There is no special case for January. The year boundary falls out of the division.

Each fiscal year is named for the two calendar years it spans, as the Nova Scotia and federal governments write it: 2024-25 runs from April 2024 to March 2025. Where the second year starts a new century it is written in full, the way the federal 1999-2000 Estimates were titled, so the year from April 2099 prints as 2099-2100 rather than 2099-00.

A recursive CTE gives every month a line, from the April that opens the first fiscal year in the log to the last month in it. The running total is a window SUM partitioned by fiscal year, so it starts again each April.

## Growth against last year

Query 04 sets each month's fiscal year-to-date against the line twelve back. Every month has a line, missing ones included, so twelve back is always the same fiscal month a year earlier. Twelve rows back in the log would not be. With December 2024 missing, every month from 2025-05 to 2025-12 would be set against the month thirteen back.

Growth is to a whole percent, worked out in whole numbers with a half rounded away from zero, so a rise and a fall of the same size print the same size. The sample holds four exact halves: 12.5 percent up at 2025-04, 2.5 up at 2026-04, 0.5 down at 2026-05 and 2.5 down at 2026-08. They print as 13, 3, -1 and -3, where rounding half to even would give 12, 2, 0 and -2.

Query 05 sets a year still running only against the same months of the year before. 2026-27 has five months, 2076373.26, against 2129613.60 for April to August 2025. The whole of 2025-26, 3457099.53, sits in the last column and plays no part in the growth: five months against twelve is not a comparison.

## A missing month

December 2024 has no row. Queries 01 and 03 to 05 read that as unknown, not zero, because a month that brought in nothing is written as 0.00: November 2024, when the ferry was laid up, is 0.00 and the 2024-25 total carries on through it at 2674272.71. From December to March the total is blank, and the last column of query 03 names 2024-12 as the reason.

The gap reaches forward. 2024-25 has no total, so 2025-26 has nothing to set its full year against, and query 04 leaves growth blank from 2025-12 to 2026-03. A month before the log starts in its first fiscal year counts as missing in the same way, so a log that begins in February leaves its first fiscal year without a total. Query 02 runs straight over the gap: 2024 has no December line, so 2025-12 has nothing to compare with, and a month missing earlier in a calendar year would add nothing to every total after it.

## Sample data

Monthly fare revenue of a fictional Nova Scotia ferry commission, one row for each month from April 2024 to August 2026 except December 2024: 28 rows in `revenue.csv`, amounts in dollars and cents. Summer carries the year. July and August are over 600000.00 each and the winter months under 170000.00. November 2024, when the ferry was laid up, is 0.00. The winter of 2026 runs well ahead of the winter before, and the summer of 2026 a little behind.

## Known limits

- The year starts in April in every query that works out a fiscal year: the three-month shift, the April the calendar starts from, and the year names are written out in queries 01, 03, 04 and 05, so each file runs on its own. A year starting in another month means changing each copy.
- A missing month is unknown. A month that should count as zero needs a row of 0.00, and one that is missing leaves every fiscal total from it to its year's end blank.
- Revenue is one figure per month, from 0.00 to 99999999.99. A month whose refunds outweigh its takings cannot be entered as a negative; it has to be settled into the months around it first.
- Growth is a percent of last year's figure and is left blank against a zero. Against a figure near zero it has no useful ceiling: 0.01 one year and 99999999.99 the next prints as 999999999800.
- Months run from 1970-01 to 2200-12, so a log holds at most 2772 rows. A field holds at most 131072 characters (the CSV parser's limit), and a line past 1000000 characters is refused before it is parsed.
- A query that runs past 20000 thousand SQLite steps is stopped with an error. Every month the loader allows, at the largest amount, takes under a twentieth of that on SQLite 3.50, 3.34 and 3.31 alike, and no log can have more months or a longer calendar.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
