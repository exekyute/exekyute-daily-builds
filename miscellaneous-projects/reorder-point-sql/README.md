# Reorder Point Queries

Five SQLite queries that set a reorder point for each part at a parts counter from its daily usage and its supplier's lead time, then replay the usage log to count how often each rule would have left the shelf empty. Safety stock is z times the daily standard deviation times the square root of the lead time, worked out in whole numbers, with the square roots taken by Newton steps in a recursive CTE. Reordering at the average lead-time demand alone runs out in 77 of the sample's 161 replenishment cycles, and adding safety stock at 95 percent brings that to 6.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-log-shape.sql` | The log at a glance: the days it covers, the parts, the rows, the units used and the rows where a part was not used. |
| `sql/02-average-rule.sql` | The reorder point at the average lead-time demand, replayed over the log: how many cycles each part has and how many run out. |
| `sql/03-reorder-point.sql` | Each part's average and standard deviation of daily usage, its lead-time demand, safety stock at z = 1.65 and reorder point. |
| `sql/04-rules-side-by-side.sql` | Both rules over the same cycles, part by part: run-outs and the units asked for at an empty shelf. |
| `sql/05-service-levels.sql` | The replay at 50, 90, 95 and 99 percent: safety stock held against the cycles that run out. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.8.3 or newer for recursive CTEs. The queries give the same rows on SQLite 3.31.1, 3.34.0 and 3.50.4.

```
cd miscellaneous-projects/reorder-point-sql
python run.py
```

That prints all five reports against the sample parts list and usage log. The test run checks the queries and the loader against hand-computed answers:

```
python run.py --test
```

Nineteen checks run. Seven on the sample cover the log's shape, the average rule's replay, the reorder points, the two rules side by side and the four service levels. The sixth checks that the reports agree wherever they share a number and that the sample stored in the opposite order, in tables with no key, gives the same five reports. The seventh prints all five and checks their column names, a rule as wide as each column, how many rows each prints and the first and last of them, with blank cells on the total lines, and that a query file that fails, has no query result, is not UTF-8 or is gone by the time it is read, or a folder named like one, stops them with a one-line message.

Four more run on logs built for the suite. A four-day log across a year end has a stretch that uses exactly its reorder point and does not run out beside one a unit over that does, an average and a lead-time demand on exact halves that round up, with a stretch that uses exactly the 3 that 2.5 rounds up to, a safety stock of exactly 33 that must not round up to 34, and one whose square is 841.03, just past 29 x 29, which has to round up to 30. It also has a squared safety stock of 15 whose Newton steps swing between 3 and 4 and still have to stop, parts with no spread and no safety stock, a lead time longer than the log that gives no cycles and a blank share, and a heavy last day in a stretch the end of the log cuts short.

A skewed log has a part used in one burst, which runs out in 1 of 10 cycles under the average rule and still 1 at every service level, also replayed on its own, a part that dips now and then, which runs out in 8 of 10, and 900 units in a stretch the end of the log cuts short, which count against neither rule. Three small logs have a part used on one day in eight, whose share of 12.5 percent has to round up to 13, a part used once in 400 days, whose standard deviation of exactly 0.05 has to print as 0.1, and one used once in 50 days, whose Newton steps swing between 2 and 3 and have to settle on 2, so it prints 0.1 and not 0.2. And 1000 parts over 100 days and 100 parts over 1000 days, at the loader's limits, have to run inside the step budget with their largest numbers exact, beside a query that would run for ever, which the budget stops.

Eight exercise the loader and the command line. They refuse the included bad log, a part listed twice for one day, units and lead times written any way but a plain whole number in range, part codes that are not capital letters and digits joined by single hyphens, at most 24 characters, in either file, and days that are not a real date written like 2026-01-31 from 1970 to 2200, each next to the values at its limits, which load. They refuse a part missing from the parts list, a day missing from one part's log, a part with no rows, a log of one day or of more than 1000, and a parts list past 1000 parts.

They count rows past blank lines, name a stray quote by its own row, refuse broken rows and a bad, renamed or reordered header in either file, and cut a long value short in the message. They refuse an empty file, one with only a header, one that is not UTF-8 from its first line or only far down, a folder, a read that gives way partway and a line past 1000000 characters, and stop a log past 100000 rows as it is read. On the command line they refuse a missing file, one of the two files given without the other and a test run on any file other than the samples, and check that output and messages go out as UTF-8 and that a message names the parts file given on the command line. The run ends with `all checks passed`.

The loader validates both files before any query runs. Point it at the included bad log to see a rejection:

```
python run.py --parts data/parts.csv --usage data/invalid-usage.csv
```

It stops at the first problem it reaches, naming the row where it has one. A byte that is not UTF-8 is the exception: the file is decoded about 8 KB at a time, so a bad byte is reported first, without a row, when a problem sits above it in the same stretch of the file. On the included bad log:

```
invalid-usage.csv row 412: units '-2' is not a whole number of units from 0 to 999, written like 4
```

## Where the average rule goes wrong

Query 02 orders when stock falls to the usage expected over the lead time: the average day times the lead days, rounded half up. The replay cuts each part's 120 days into back-to-back stretches one lead time long, counted from the first day, and each whole stretch is a cycle that starts with the stock at the reorder point and ends with the delivery. A stretch that uses more than that runs out first. 77 of the 161 cycles do, 48 percent, from 3 of 10 for LED-TUBE-4FT to 5 of 8 for FUSE-15A.

When usage is steady and as likely to run high as low, the average sits in the middle of what a lead time uses. A stretch runs over it about as often as under, so ordering at the average leaves every delivery to a coin toss.

## Safety stock in whole numbers

Query 03 adds safety stock: z times the daily standard deviation times the square root of the lead time, with z = 1.65 for about 95 percent. The standard deviation comes from the spread, n times the sum of squares minus the square of the sum, which is exact in whole numbers. The same sum taken as the average of the squares minus the squared average, in floating point, can cancel away on large values.

SQLite has no square root before 3.35, and it is optional after. Rather than register a Python function in `run.py`, queries 03 to 05 take the root in SQL: a recursive CTE runs Newton steps on whole numbers, x becoming (x + m / x) / 2 until it stops falling, which leaves the largest whole number whose square is at most m. That keeps every query runnable on SQLite builds that have no math functions and no Python beside them.

Safety stock is rounded up to a whole unit, since rounding it down would fall short of the service level, and lead-time demand is rounded half up. Rounding the squared safety stock up and then taking the root, plus one unless it is a perfect square, gives the same whole number as rounding up the exact safety stock. GLOVE-NITRILE-L uses 24.1 a day with a standard deviation of 6.1 on a five-day lead time: 121 units of lead-time demand and 23 of safety stock, a reorder point of 144.

## Both rules over the same cycles

Query 04 replays both rules over the same stretches. With safety stock, 6 of the 161 cycles run out instead of 77, and the units asked for at an empty shelf fall from 642 to 21. Three parts never run out at all. GLOVE-NITRILE-L's first cycle uses exactly its 144 and ends at zero without running out; equal is enough.

## Service levels

Query 05 runs the replay at four levels, z = 0 being the average rule. The eight parts hold 110, 141 and 198 units of safety stock at 90, 95 and 99 percent, and the cycles that run out drop from 77 to 15, 6 and 1, which is 9, 4 and 1 percent. The last points cost the most: going from 95 to 99 percent adds 57 units to save 5 run-outs, where going from the average rule to 90 percent took 110 units to save 62.

## Sample data

Eight parts at the counter of a fictional maintenance shop that is open every day, logged from 2026-01-01 to 2026-04-30: 960 rows in `usage.csv`, and each part's supplier lead time, from 3 to 14 days, in `parts.csv`. Each part's days were drawn at random around a steady average, from a little over one fuse a day to 59.2 shop towels, so the sample fits the steady-usage assumption. 69 rows are days a part was not used, written as 0. FILTER-20X25's average of 3.65 and its lead-time demand of 36.5 land on exact halves.

## Known limits

- The formula assumes steady usage, where one day tells nothing about the next, a lead time that does not vary, and usage over a lead time close enough to a normal curve for z to carry its percentage. A part used in bursts breaks it: the suite's part with one 20-unit day in 20 runs out in 1 of its 10 cycles at every level from 50 to 99 percent.
- Each reorder point is worked out from the same log it is replayed against, so the replay checks the rule on the history it came from. It is not a forecast.
- The replay places each order the moment stock reaches the reorder point and brings the delivery at the close of the lead time's last day. A counter that checks stock once a day usually finds it a little under the reorder point by the time it orders, so its cycles start with less stock than the replay assumes and run out more often.
- Stretches are counted from the first day of the log, and one cut short by the end of the log is left out. Starting a day later groups the days differently and can change the counts, and a part whose lead time is longer than the log gets no cycles at all.
- The z values are written into the queries: 1.65 as 27225, which is 1.65 x 1.65 x 10000, in queries 03 and 04, and four levels in hundredths in query 05. Changing one means changing each copy.
- Every part needs a row for every day of the log, with 0 on a day it was not used. A part code is capital letters and digits joined by single hyphens, at most 24 characters, a day is from 1970-01-01 to 2200-12-31, usage is 0 to 999 units a day, a lead time is 1 to 90 days, and a log covers at most 1000 days, 1000 parts and 100000 rows. A line of a file holds at most 1000000 characters, and a field at most 131072, the CSV parser's limit. A file is decoded in blocks of about 8 KB, so a byte that is not UTF-8 is reported ahead of a problem on an earlier row in the same block.
- A query that runs past a hundred million SQLite steps is stopped with an error. The costliest logs found within the limits take about a quarter of that on 3.31, 3.34 and 3.50 alike; the older versions work a named CTE out again at every mention, which is why each query names its dearest steps once.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
