# Marketing Attribution Queries

Given a log of marketing touches and one of conversions, each conversion's revenue is credited to the channels behind it by first touch, last touch and a linear split. A touch counts only in the 30 days before a conversion and after the customer's previous one, and each model's credit adds back to the revenue to the cent, with conversions that have no touch in their window on a line of their own. A plain join of every touch to every conversion by customer credits 6459.74 on a sample that holds 2628.07 of revenue.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-log-shape.sql` | The two logs at a glance: touches, channels and customers touched, conversions, customers converting, and the revenue. |
| `sql/02-naive-join.sql` | Revenue by channel from a plain join of touches to conversions on the customer, with its total. |
| `sql/03-touch-windows.sql` | For each conversion, where its window opens, how many touches fall in it, why each other touch by that customer does not count, and the first and last channel. |
| `sql/04-credit-by-conversion.sql` | Each conversion's revenue credited to channels under the three models, split to the cent. |
| `sql/05-channel-totals.sql` | Channel totals under the three models with the join beside them, an unattributed line, and lines that show whether each adds up to the revenue. |

## Running it

Python 3.7 or newer and its standard library are enough, with SQLite 3.25 or newer for window functions; SQLite 3.31.1, 3.34.0 and 3.50.4 give the same rows.

```
cd miscellaneous-projects/attribution-sql
python run.py
```

Run bare, it prints the five reports for the sample logs. The suite runs the queries and the loader against hand-computed answers:

```
python run.py --test
```

The suite has eighteen checks and ends on `all checks passed`. Seven use the sample: one per report, a cross-check and a print check. The cross-check holds each conversion's credit to its revenue under all three models, query 05's lines to query 04 added up by channel and to its total, its join column to query 02, and query 03 to putting every touch into exactly one of its four counts for each conversion.

The print check covers column names, the rule under them, how many rows each report prints and the first of them, and a missing value printing as a blank cell. A query file that fails, has no query result, is not UTF-8 or is gone by the time it is read, a folder named like one, or a query folder that is empty or not there has to stop the run with a one-line message.

Four use logs built to order:

- Touches on every edge of the window across a change of year and a leap February: exactly 30 days before, a minute more, at the moment of the conversion, and at the moment of a previous conversion exactly 30 days earlier. Beside them are a conversion whose touches all come after it, a channel touched only by a customer who never converted, and enough untouched revenue that the join comes in under the revenue.
- Touch and conversion ids running against time, so the previous conversion and the first and last touch have to be found by time, in the credit and the channel totals alike; and the sample stored in the opposite order in tables with no key.
- Six cents shared among seven channels, a conversion worth nothing, and a channel with three of four touches cut down from its whole share.
- 50000 customers with a touch and a conversion each, 25000 with two touches before two conversions, and one customer with 50000 touches on 50000 channels beside 49998 conversions no touch reached, all inside the step budget, beside a query that would run for ever, which the budget stops.

Seven check the loader and the command line. They refuse:

- the included bad touch log, a touch_id or conversion_id listed twice, a touch logged twice, and a customer converting twice in one minute
- ids with a leading zero, a sign or a point
- customer codes and channel names in the wrong case, with a space or a stray hyphen, accented, in fullwidth letters or too long
- moments on days that do not exist, with seconds, a T or no time at all, or outside 1970 to 2200, and revenue written any way but like 149.99
- bad headers in either log, empty files, text that is not UTF-8, a folder and a line past 1000000 characters
- logs past 50000 touches or 50000 conversions, stopped as they are read, and logs whose touches and conversions pair up more than 100000 times by customer, while two logs of exactly 50000 rows each that pair up exactly 100000 times load
- on the command line, one log without the other, a missing file, a name with a wildcard in it and a test run on any files other than the samples

They also count rows past blank lines, the same with Windows line endings, name a stray quote by its own row, and check that output and messages go out as UTF-8 and that main prints the reports for a pair of your own.

The loader validates both logs before any query runs. To see it refuse the included bad touch log:

```
python run.py --touches data/invalid-touches.csv --conversions data/conversions.csv
```

It stops at the first problem it reaches, naming the row where it has one. A byte that is not UTF-8 is the exception: the file is decoded about 8 KB at a time, so a bad byte can be reported first, without a row, when a problem sits above it in the same stretch of the file. On the included bad touch log:

```
invalid-touches.csv row 25: touched_at '2026-04-31 09:30' is not a date and time written like 2026-04-15 14:00, from 1970-01-01 00:00 to 2200-12-31 23:59
```

## Every touch against every conversion

Query 02 joins every touch to every conversion by the same customer and gives each touch's channel the whole revenue of its paired conversion. On the sample that makes 55 pairs over 14 conversions and credits 6459.74, against 2628.07 in the conversions log. Query 03 sorts the same 55 pairs: 32 fall in a window, 9 are touches made after their conversion, 9 came at or before the customer's previous conversion, and 5 are more than 30 days old.

CU-1002 shows the first fault. Their affiliate touch on 2026-04-10 comes after both their conversions, yet the join hands affiliate 240.00 and 57.35 for it. Affiliate ends with 462.34 from the join and nothing under any model, since its other two touches are more than 30 days older than their paired conversions.

The repeat is the second. CU-1005 converted on 2026-04-04 and again two days later with no touch between, and the join credits the first conversion's email and paid-search touches with the second's 64.00 as well. Even a pair inside a window takes the whole revenue, so conversion 13, reached by seven touches, counts seven times over.

Conversion 4, which no touch reached, drops out of the join and is reported nowhere. On a log where untouched conversions outweigh the double counting, the join comes in under the revenue instead.

## Drawing the window

A touch counts toward a conversion when it is at most 30 days before it, no later than it, and after the customer's previous conversion. The lookback runs to the minute: conversion 10 at 2026-04-15 14:00 counts an email at 2026-03-16 14:00, exactly 30 days before, and drops a referral one minute earlier. A touch at the moment of the conversion counts toward it, as the paid-search touch does there, and one at the moment of a previous conversion belongs to that one, so no touch counts twice.

CU-1012 shows the last rule: their email at 2026-04-08 16:20, the last touch of conversion 9 in the same minute, does not count again toward their conversion on 2026-04-20. The window takes whichever start is later. CU-1001's second conversion on 2026-05-20 looks back only to 2026-04-20, so a display touch from 2026-04-02 is too old though it came after their first conversion.

Moments are held as text in one form, `2026-04-15 14:00`, so comparing them as text compares them in time, and strftime writes the lookback in the same form. `datetime()` would add seconds, and `'2026-03-16 14:00'` sorts before `'2026-03-16 14:00:00'`, which would drop the touch made exactly 30 days before.

Touches in the same minute go in the order they reached the log, by touch_id. Conversion 13 opens with three touches at 2026-04-20 08:00, ids 21, 22 and 23, so paid-search, the lowest, is first, and closes with three at 2026-05-08 09:00, so organic, id 29, is last. Partner touches reach the log later than the rest, so touch ids do not follow time and settle only a tie within one minute.

## Three models, to the cent

First touch gives a conversion's whole revenue to the channel of the earliest touch in its window, last touch to the latest. Linear shares it by touch, so a channel with two of four touches earns half. Each share is first cut down to the whole cent in whole-number arithmetic, and the cents left over go one each to the channels that lost most in the cut, a tie going to the channel whose name sorts first.

Conversion 13 is 150.25 over seven touches, and the cut leaves three cents. Email and social, with two touches each, lose six sevenths of a cent and take one cent each: 42.93. Display, organic and paid-search each lose three sevenths, so the third cent goes to display by name: 21.47, 21.46 and 21.46. On conversion 14, 99.99 over two email touches, one social and one referral, the two single touches lose more than email and take both leftover cents: email 49.99, social 25.00, referral 25.00.

Three conversions have no touch in their window: conversion 3, whose touches are all more than 30 days old, conversion 4 with none at all, and CU-1005's second. Their 449.00 goes on the `(unattributed)` line under every model. Each model then comes to 2628.07, over the revenue by 0.00, while the join comes to 6459.74, over by 3831.67.

The model moves the credit. Social earns 60.00 as a first touch, nothing as a last touch and 180.36 linear; referral earns 1254.99, 1349.99 and 1277.49, most of it from one 1250.00 conversion with a single touch.

## Sample data

A fictional online shop's touch log, `touches.csv`, and conversions log, `conversions.csv`, in whole minutes with revenue to the cent. The 40 touches come from 11 customers over seven channels, and the 15 conversions from 11 customers, four of whom converted twice; one customer touched never converted, and one who converted was never touched. Touches on the site are numbered in time order, 1 to 33, and the partner channels, affiliate and referral, reported later as 34 to 40.

A log of your own needs the same headers: `touch_id,customer,channel,touched_at` and `conversion_id,customer,converted_at,revenue`. Ids are whole numbers from 1 to 999999999. Customer codes are capital letters and digits joined by single hyphens, and channel names small letters and digits joined the same way, each at most 24 characters. Moments are written like `2026-04-15 14:00` and revenue like `149.99`.

## Known limits

- Moments are to the minute and carry no time zone, so both logs have to be written in one zone. Kept in local time, a window that spans a change of clocks covers an hour more or less than 30 days.
- The 30-day lookback is written into queries 03, 04 and 05. Changing it means changing each copy.
- Linear credit goes by touch, so a channel that reaches a customer five times outweighs one that reaches them once. Position-based and time-decay models are not among the three.
- The tie rules are conventions, not findings. Two touches in one minute go by touch_id, and when channels lose the same amount in the linear split's cut, the one whose name sorts first takes the leftover cent.
- The same customer on the same channel in the same minute is refused as a touch logged twice, even if two real touches happened then, and a customer converting twice in one minute is refused; the two orders need adding into one.
- A log holds at most 50000 touches and 50000 conversions, and they may pair up at most 100000 times by customer. A line holds at most 1000000 characters, and a field at most 131072, the CSV parser's limit. A file is decoded in blocks of about 8 KB, so a byte that is not UTF-8 can be reported ahead of a problem on an earlier row in the same block.
- A query that runs past two hundred million SQLite steps is stopped with an error. The costliest logs found within the limits take under a third of that on 3.31, 3.34 and 3.50 alike. The older two work a named CTE out again in every SELECT that names it, so each CTE in queries 03 to 05 is named only once.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
