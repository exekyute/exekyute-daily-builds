# Marketing Attribution Queries

Five SQLite queries that credit each conversion's revenue to the marketing channels that led to it, by first touch, last touch and a linear split. A touch counts toward a conversion only when it falls in the 30 days before it and after the customer's previous conversion, and each model's credit adds back to the revenue to the cent, with conversions that have no touch in their window reported on a line of their own. Joining every touch to every conversion by customer instead, the obvious way, credits 6459.74 on a sample that holds 2628.07 of revenue.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-log-shape.sql` | The two logs at a glance: touches, channels and customers touched, conversions, customers converting, and the revenue. |
| `sql/02-naive-join.sql` | Revenue by channel from a plain join of touches to conversions on the customer, with its total. |
| `sql/03-touch-windows.sql` | For each conversion, where its window opens, how many touches fall in it, why each other touch by that customer does not count, and the first and last channel. |
| `sql/04-credit-by-conversion.sql` | Each conversion's revenue credited to channels under the three models, split to the cent. |
| `sql/05-channel-totals.sql` | Channel totals under the three models with the join beside them, an unattributed line, and lines that show whether each adds up to the revenue. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.25 or newer for window functions. The queries give the same rows on SQLite 3.31.1, 3.34.0 and 3.50.4.

```
cd miscellaneous-projects/attribution-sql
python run.py
```

That prints all five reports against the sample logs. The test run checks the queries and the loader against hand-computed answers:

```
python run.py --test
```

Eighteen checks run. Seven on the sample cover the logs' shape, the join, the windows, the credit per conversion and per channel, and a cross-check between the reports: each conversion's credit adds back to its revenue under all three models, query 05's lines are query 04 added up by channel and add up to its total, its join column is query 02, and query 03 puts every touch into exactly one of its four counts for each conversion. The seventh prints all five reports and checks their column names, the rule under them, how many rows each prints and the first of them, that a missing value prints as a blank cell, and that a query file that fails, has no query result, is not UTF-8 or is gone by the time it is read, a folder named like one, or a query folder that is empty or not there, stops them with a one-line message.

Four more run on logs built for the suite. The first puts touches on every edge of the window across a change of year and a leap February: exactly 30 days before, a minute more than that, at the moment of the conversion, and at the moment of a previous conversion that falls exactly 30 days earlier, along with a conversion whose touches all come after it, a channel that only a customer who never converted touched, and enough untouched revenue that the join comes in under the revenue. The second runs touch ids and conversion ids against time, so the previous conversion and the first and last touch have to be found by time in the credit and the channel totals alike, and stores the sample in the opposite order in tables with no key. The third shares six cents among seven channels, credits a conversion worth nothing, and cuts a channel with three of four touches down from its whole share, and the fourth runs 50000 customers with a touch and a conversion each, 25000 customers with two touches before two conversions, and one customer with 50000 touches on 50000 channels beside 49998 conversions no touch reached, all inside the step budget, beside a query that would run for ever, which the budget stops.

Seven exercise the loader and the command line. They refuse the included bad touch log, a touch_id or conversion_id listed twice, a touch logged twice and a customer converting twice in one minute; ids with a leading zero, a sign or a point; customer codes and channel names in the wrong case, with a space or a stray hyphen, accented, in fullwidth letters or too long; moments on days that do not exist, with seconds, a T or no time at all, or outside 1970 to 2200; and revenue written any way but like 149.99. They count rows past blank lines, name a stray quote by its own row, refuse bad headers in either log, empty files, text that is not UTF-8, a folder and a line past 1000000 characters, count rows the same with Windows line endings, and stop a log past 50000 touches or 50000 conversions as it is read.

They refuse logs whose touches and conversions pair up more than 100000 times by customer, and load two logs of exactly 50000 rows each that pair up exactly 100000 times. On the command line they refuse one log without the other, a missing file, a name with a wildcard in it and a test run on any files other than the samples, and check that output and messages go out as UTF-8 and that main prints the reports for a pair of your own. The run ends with `all checks passed`.

The loader validates both logs before any query runs. Point it at the included bad touch log to see a rejection:

```
python run.py --touches data/invalid-touches.csv --conversions data/conversions.csv
```

It stops at the first problem it reaches, naming the row where it has one. A byte that is not UTF-8 is the exception: the file is decoded about 8 KB at a time, so a bad byte can be reported first, without a row, when a problem sits above it in the same stretch of the file. On the included bad touch log:

```
invalid-touches.csv row 25: touched_at '2026-04-31 09:30' is not a date and time written like 2026-04-15 14:00, from 1970-01-01 00:00 to 2200-12-31 23:59
```

## Where the join goes wrong

Query 02 joins every touch to every conversion by the same customer and hands each touch's channel the whole revenue of the conversion it is paired with. On the sample that makes 55 pairs over 14 conversions and credits 6459.74, while the conversions log holds 2628.07. Query 03 sorts the same 55 pairs: 32 fall in a window, 9 are touches made after the conversion they are paired with, 9 came at or before the customer's previous conversion, and 5 are more than 30 days old.

Customer CU-1002 shows the first fault. Their affiliate touch on 2026-04-10 comes after both of their conversions, and the join still hands affiliate 240.00 and 57.35 for it. Affiliate ends with 462.34 from the join and nothing under any model, since its other two touches are more than 30 days older than the conversions they are paired with.

The second fault is the repeat. CU-1005 converted on 2026-04-04 and again two days later with no touch in between, and the join credits the first conversion's email and paid-search touches with the second conversion's 64.00 as well. Even a pair inside a window takes the whole revenue, so conversion 13, reached by seven touches, counts seven times over, and conversion 4, which no touch reached, drops out of the join and is reported nowhere. On a log where untouched conversions outweigh the double counting, the join comes in under the revenue instead.

## Drawing the window

A touch counts toward a conversion when it is no more than 30 days before it, no later than it, and after the customer's previous conversion. The lookback runs to the minute: conversion 10 at 2026-04-15 14:00 counts an email at 2026-03-16 14:00, exactly 30 days before, and drops a referral one minute earlier. A touch at the same moment as the conversion counts toward it, as the paid-search touch does there, and a touch at the same moment as a previous conversion belongs to that one, so no touch counts twice.

CU-1012 shows the last rule. Their email at 2026-04-08 16:20 is the last touch of conversion 9, made in the same minute, and it does not count again toward their conversion on 2026-04-20. The window takes whichever start comes later: CU-1001's second conversion on 2026-05-20 looks back only to 2026-04-20, so a display touch from 2026-04-02 is too old even though it came after their first conversion.

Moments are held as text in one form, `2026-04-15 14:00`, so comparing them as text compares them in time. The lookback is written by strftime in that same form. `datetime()` would add seconds, and `'2026-03-16 14:00'` sorts before `'2026-03-16 14:00:00'`, which would drop the touch made exactly 30 days before.

Touches made in the same minute are taken in the order they reached the log, by touch_id. Conversion 13 opens with three touches at 2026-04-20 08:00, ids 21, 22 and 23, so paid-search, the lowest, is the first touch, and closes with three at 2026-05-08 09:00, so organic, id 29, is the last. Partner touches reach the log later than the rest, which is why touch ids do not follow time and only settle a tie within one minute.

## Three models, to the cent

First touch gives a conversion's whole revenue to the channel of the earliest touch in its window, and last touch to the latest. Linear shares it by touch, so a channel with two of four touches earns half. Each channel's share is cut down to the whole cent first, in whole-number arithmetic, and the cents that leaves over go one each to the channels that lost the most in the cut, a tie going to the channel whose name sorts first.

Conversion 13 is 150.25 over seven touches, and the cut leaves three cents over. Email and social, with two touches each, lose six sevenths of a cent in the cut and take one cent each, 42.93. Display, organic and paid-search each lose three sevenths, so the third cent goes to display by name: 21.47, 21.46 and 21.46. On conversion 14, 99.99 over two email touches, one social and one referral, the two single touches lose more in the cut than email does, so they take both leftover cents: email 49.99, social 25.00, referral 25.00.

Three conversions have no touch in their window: conversion 3, whose touches are all more than 30 days old, conversion 4 with none at all, and CU-1005's second conversion. Their 449.00 goes on the `(unattributed)` line under every model. Each model then comes to 2628.07, over the revenue by 0.00, while the join comes to 6459.74, over by 3831.67.

The model moves the credit. Social earns 60.00 as a first touch, nothing as a last touch and 180.36 linear, and referral earns 1254.99, 1349.99 and 1277.49, most of it from one 1250.00 conversion with a single touch.

## Sample data

A fictional online shop's touch log, `touches.csv`, and conversions log, `conversions.csv`, in whole minutes with revenue to the cent. The 40 touches come from 11 customers over seven channels, and the 15 conversions from 11 customers, four of whom converted twice; one customer touched never converted and one who converted was never touched. Touches on the site are numbered in time order, 1 to 33, and the partner channels, affiliate and referral, reported later as 34 to 40.

A log of your own needs the same headers: `touch_id,customer,channel,touched_at` and `conversion_id,customer,converted_at,revenue`. Ids are whole numbers from 1 to 999999999, customer codes are capital letters and digits joined by single hyphens, and channel names are small letters and digits joined the same way, each at most 24 characters. Moments are written like `2026-04-15 14:00` and revenue like `149.99`.

## Known limits

- Moments are to the minute and carry no time zone, so both logs have to be written in one zone. Kept in local time, a window that spans a change of clocks covers an hour more or less than 30 days.
- The 30-day lookback is written into queries 03, 04 and 05. Changing it means changing each copy.
- Linear credit goes by touch, so a channel that reaches a customer five times outweighs one that reaches them once. Position-based and time-decay models are not among the three.
- The tie rules are conventions, not findings. Two touches in one minute go by touch_id, and when channels lose the same amount in the linear split's cut, the one whose name sorts first takes the leftover cent.
- The same customer on the same channel in the same minute is refused as a touch logged twice, even if two real touches happened then, and a customer converting twice in one minute is refused; the two orders need adding into one.
- A log holds at most 50000 touches and 50000 conversions, and they may pair up at most 100000 times by customer. A line holds at most 1000000 characters, and a field at most 131072, the CSV parser's limit. A file is decoded in blocks of about 8 KB, so a byte that is not UTF-8 can be reported ahead of a problem on an earlier row in the same block.
- A query that runs past two hundred million SQLite steps is stopped with an error. The costliest logs found within the limits take under a third of that on 3.31, 3.34 and 3.50 alike, though the older two work a named CTE out again at every mention, which is why each CTE in queries 03 to 05 is named only once.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
