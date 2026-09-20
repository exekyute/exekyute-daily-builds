# Delivery Histogram Queries

Five SQLite queries that turn a log of delivery times into a histogram of ten-minute bins, each reading being the minutes a van ran early or late. The bins are built first, by a recursive CTE running from the lowest bin to the highest, and the counts are joined onto them, so a bin nothing lands in still prints. Grouping on the minutes divided by ten instead, the obvious way, goes wrong twice on the sample: dividing toward zero piles 86 deliveries into the bin at zero that holds 50, and 12 empty bins never print at all.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-log-shape.sql` | The log at a glance: how many deliveries, the earliest and latest reading, and how many ten-minute bins lie between them, with and without readings. |
| `sql/02-naive-histogram.sql` | The histogram from a plain GROUP BY on the minutes divided by ten, bins and headings as it prints them. |
| `sql/03-histogram.sql` | Every bin from the lowest to the highest, with its count, a running count, its share of the log and a bar. |
| `sql/04-naive-against-true.sql` | The two histograms bin by bin, and what went wrong in each bin the quick one gets wrong. |
| `sql/05-bin-widths.sql` | The same readings at five, ten and thirty minutes a bin: bins, empty bins, the longest run of them, and the fullest bin. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.25 or newer for window functions.

```
cd miscellaneous-projects/histogram-bins-sql
python run.py
```

That prints all five reports against the sample log. The test run checks the queries and the loader against hand-computed answers:

```
python run.py --test
```

Eighteen checks run. Six on the sample cover the log's shape, the quick histogram, every bin with its running count, share and bar, the two histograms bin by bin, and the same readings at three widths. The sixth prints all five reports and checks their column names, a rule as wide as each column, how many rows each prints and the first of them, that a query file that fails, has no query result, is not UTF-8 or is gone by the time it is read, or a folder named like one, stops them with a one-line message, and that a value the printer is handed as nothing comes out as a blank cell.

Five more run on logs built for the suite: readings that sit exactly on bin boundaries, where -1 has to land in the bin at -10 and -20 in the bin that starts there; a log where every van ran early, on which the quick query invents a bin above them all that the comparison still has to print, and every bin width still has to reach the reading nearest zero; a log of a single reading, which is one bin at 100 percent with no gap at any width; shares that land on an exact half, which have to round up where printf or ROUND on a float, or rounding half to even, would round down, next to a bin too small for a bar of its own that still shows one; and 100000 readings spread across the whole range, 289 bins at ten minutes and 577 at five, which have to run inside the step budget, beside a query that would run for ever, which the budget stops.

Seven exercise the loader and the command line. They refuse the included bad log, which has a reading written as a fraction, and a delivery listed twice; minutes with a fraction, a plus sign, a leading zero, written as -0, past a day either way, blank, in exponent form, with two minus signs, as a word or in Arabic-Indic digits, next to a full day either way and 0, which load; and delivery codes in lower case, with a space, a doubled or outer hyphen, an accent, too long or blank, next to one of exactly 24 characters with two hyphens, which loads.

They count rows past blank lines and a line of spaces, name a stray quote by its own row, in a data row or in the header, refuse rows with too many or too few fields, a line of commas, a tab, text after a closing quote, a quote left open, a field past the parser's limit and a bad, renamed or reordered header, also one written as a single quoted field or with a trailing comma, and cut a long value or header short in the message, by one character as well as by many.

They refuse an empty file, one of blank lines, one with only a header, one that is not UTF-8 from its first line or only far down, or holds only part of a byte-order mark, a folder, a read that gives way partway and a line past 1000000 characters, while a byte-order mark, blank lines before the header, spaces around unquoted fields and a line holding one empty quoted field, which is passed over like a blank one, load. They stop a log past 100000 readings as it is read, before a bad byte further down, and load one of exactly 100000. On the command line they refuse a missing file, a name with a wildcard in it and a test run on any file other than the sample, and check that output and messages go out as UTF-8. The run ends with `all checks passed`.

The loader validates the log before any query runs. Point it at the included bad log to see a rejection:

```
python run.py --deliveries data/invalid-deliveries.csv
```

It stops at the first problem it reaches, naming the row where it has one:

```
invalid-deliveries.csv row 61: minutes '12.5' is not a whole number of minutes from -1440 to 1440, written like -15 or 20
```

## Where the quick histogram goes wrong

Query 02 groups on the minutes divided by ten. SQLite divides whole numbers toward zero, so -9 / 10 and 9 / 10 are both 0: the bin at zero collects everything from -9 to 9, nineteen minutes wide against ten, and comes to 86 deliveries where the bin from 0 to 9 holds 50. The headings below zero are wrong with it: the bin printed as -10 to -1 holds -19 to -10 instead, so of the 39 readings that belong under that heading it keeps only the 3 sitting exactly on -10, and takes in 6 from further down, 9 in all. The bin printed as -30 to -21 holds the readings from -39 to -30.

GROUP BY can only return a bin some row falls in, so the 12 empty bins never print. The sample's deliveries run from 34 minutes early to 181 late, and between 40 and 69 late there is nothing at all, a stretch three bins wide that the quick report shows as 30 to 39 sitting next to 70 to 79. Query 04 puts the two side by side: 36 too many at zero, 30 missing from the bin below, and 13 bins the quick query never mentions.

## Building the bins

Query 03 rounds the division down rather than toward zero, by taking nine off a negative reading first: `(minutes - 9 * (minutes < 0)) / 10`. In SQLite a comparison is 1 or 0, so that subtracts nine only below zero, which sends -1 to the bin at -10 and leaves 1 in the bin at 0.

A bin runs from its own multiple of ten up to nine past it, so a reading exactly on a boundary belongs to the bin that starts there: -10 and 20 open their bins rather than closing the ones before. The bins themselves come from a recursive CTE counting from the lowest bin any reading falls in to the highest, and the counts are joined onto that list, so an empty bin prints at zero with a blank bar.

Shares are worked out in whole numbers and rounded half up to a tenth of a percent. Held as a float, 0.85 percent sits just under the half: SQLite 3.50's printf prints it as 0.8 and 3.31 and 3.34 print 0.9, so a share held as a float would change with the SQLite version.

## Bin width

Query 05 runs the same readings at three widths. At five minutes a bin the log spreads over 44 bins, 26 of them empty, with a 16-bin stretch of nothing in the tail. At ten it is 23 bins and an 8-bin stretch. At thirty it fits in 9 bins, the gap shrinks to 2, and the fullest bin holds 70 of the 126 deliveries.

The shape is smoother at thirty, and the quiet stretch in the tail is nearly gone with it. The width is a choice, and it decides what the histogram shows.

## Sample data

126 deliveries by a fictional courier, each a whole number of minutes early as a minus or late as a plus: `deliveries.csv`, sorted by delivery code. Most land within ten minutes either way, 50 run early, 19 sit exactly on a bin boundary, and three long tails are a single delivery each, at 72, 95 and 181 minutes late.

## Known limits

- A reading is a whole number of minutes from -1440 to 1440, a day either way, and a log holds at most 100000 of them. A line of the file holds at most 1000000 characters, and a field at most 131072, the CSV parser's limit.
- The bin width is written into each query: ten minutes in queries 01 to 04, and five, ten and thirty in query 05. Changing it means changing each copy.
- Bins start at a multiple of the width, so the bin holding zero runs from 0 to 9 rather than being centred on it. A histogram meant to show early and late as mirror images would need bins placed around zero instead.
- The bar is drawn against the fullest bin, not against a fixed scale, so bars from two different logs cannot be compared.
- The log carries no dates, routes or drivers, so the queries cannot show whether the tail belongs to one route or one bad afternoon.
- A query that runs past a hundred million SQLite steps is stopped with an error. The costliest log the limits allow takes under a tenth of that, on 3.31 and 3.34 as much as on 3.50, though those older versions work a named CTE out again at every mention, which is why each query names its dearest step once.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
