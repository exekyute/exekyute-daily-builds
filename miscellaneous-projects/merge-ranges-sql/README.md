# Merge Ranges Queries

Five SQLite queries that turn overlapping coverage periods into the stretches a customer was actually covered for. Two answers come easily and each is wrong in its own direction: adding every period up counts a renewed-early customer's overlap twice, and taking the first start to the last end paves over every lapse. Merging the periods first gives the number neither of them has. In the sample, adding up says one customer had 390 days of cover and the span says 303, where the real answer is 299 with a four-day lapse in October.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-period-log-shape.sql` | The log at a glance: customers, periods, the dates they run between, and the days you get by adding every period up. |
| `sql/02-naive-totals.sql` | The two easy answers per customer, the added-up days and the span, neither of them reliably the days covered. |
| `sql/03-merged-blocks.sql` | The periods merged into blocks of continuous cover, with the dates, the periods folded in, and the length of each. |
| `sql/04-coverage.sql` | The days covered per customer, and how far each easy answer was out. |
| `sql/05-gaps.sql` | The lapses between blocks, dated from the day after cover ends to the day before it resumes. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.25 or newer for window functions.

```
cd miscellaneous-projects/merge-ranges-sql
python run.py
```

That prints all five reports against the sample log. The test run checks the queries and the loader against hand-computed answers:

```
python run.py --test
```

Fifteen checks run. Five on the sample cover the log's shape, both naive totals, the seven merged blocks with their numbering per customer, the covered days with the error in each naive total, and the two lapses with their dates. Six on logs built for the suite cover a period that starts the day after the last one ends and one that starts a day later than that, periods held inside a longer one, February 29, a period across the year end, periods with the same dates twice and three times over, and a log whose ids run counter to its dates with a two-period block after a lapse. The first, the leap day and the year end are checked in the totals as well as the blocks, so the merge is pinned in all three files. Four exercise the loader: a period that ends before it starts; row numbers past blank lines and a stray quote, along with text after a closing quote, a repeated period_id, an id with a leading zero or ten digits, and a date written without its leading zeroes or on the first data row; a control character, a zero-width space, rows with too many or too few fields, a renamed header, dates outside the range at either end, an empty file, one with only a header, and one that is not UTF-8, next to a byte-order mark it reads through; and one customer written two ways, a blank name, a name whose spacing and accents are tidied up, and a name spelled with a zero-width joiner, which is kept. The run ends with `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --periods data/invalid-periods.csv
```

It stops at the first problem, naming the row when the problem is in one: `invalid-periods.csv row 4: period 3 ends on 2026-06-15, before it starts on 2026-08-31`. A period that ends before it starts has a length of zero or less, and period 3 here is 76 days short of zero, which takes days off the added-up total, gives the merge a block whose dates run backwards and whose length eats into the days the other periods covered, and leaves query 05 reporting a lapse that never happened.

## The two easy answers

Query 02 gives both. Adding the periods up is right only when nothing overlaps: Brightside Dental renewed on June 15 while cover ran to June 30, so 16 days are counted twice and 259 days of cover are claimed on a calendar that only holds 243. The span, first start to last end, is right only when nothing lapses: Harbour Freight Co was covered for 121 days across two spells two months apart, but its span reads 182. Kestrel Media gets both wrong at once, 390 against 303, with the real answer below both.

## Merging the periods

Query 03 reads each customer's periods in start order and compares each one with how far cover already reaches, which is the `MAX` of every end date before it, taken with a frame that stops one row short of the current row. A period opens a new block when nothing comes before it, or when it starts more than a day after that reach, since a period starting the day after the last one ends continues the cover rather than breaking it. Flagging the openers and running a `SUM` over that flag numbers the blocks, and grouping by the number gives each block its dates, its length, and how many periods folded into it.

The running `MAX` is what makes the frame worth the trouble. Comparing each period with the row before it instead would hold up until a short period sits inside a long one: Kestrel Media has a February to September period with an April period and a June to July period inside it, and the row-before test would call June a fresh block, since April ended in April. The sample would then report three blocks for Kestrel where there are two, and query 05 would date two lapses that never happened, one of 65 days from August into October and one whose dates run backwards.

## What was covered, and what was missed

Query 04 adds the blocks up per customer and prints the covered days beside the added-up total, with a column for how far each easy answer was out: days counted twice is the added-up total less the covered days, a surplus rather than a count of the days it happened on, and days not covered is the span less the covered days. Brightside Dental is 16 and 0, Harbour Freight Co is 0 and 61, and Kestrel Media is 91 and 4. Query 05 dates the lapses: Harbour Freight Co was uncovered from March 1 to April 30, and Kestrel Media from October 1 to October 4. A customer covered throughout has no rows there at all.

## Sample data

Sixteen coverage periods for five fictional customers, running from January 1 to November 30, 2026. One customer renewed twice, once early, one let cover lapse for two months, one has two short periods inside a long one and a four-day lapse after it, one renewed daily across a working week with the same day bought twice, and one has a single period. The file is deliberately not in date order.

## Known limits

- Both ends of a period are covered days, so a period from the 1st to the 1st is one day long and one ending on the 31st runs up to midnight. A log where the end date is the first uncovered day needs the plus one dropped from every period, block, and span length, the day shifts and the minus one dropped from the gap in query 05, and the plus one day dropped from the contiguity test.
- Dates only, with no times. Cover that starts or ends partway through a day, or two periods that meet at noon, cannot be told apart from whole days here.
- Periods are merged per customer, by the name as written. The loader tidies the spacing and the accents in a name and refuses a second spelling that differs only in letter case, since one customer under two spellings would come out as two customers, each covered for part of the time, with the lapse between them missing from query 05 altogether. Letter case is compared with casefold, which reads the German sharp s as ss, so two names that differ only there are refused as one. Names are kept as written otherwise, so a name spelled with a zero-width joiner in one row and without it in another still counts as two customers.
- Nothing distinguishes what the cover was for. Two periods of different products or policies merge into one block, and a log where that matters needs the product in the grouping alongside the customer.
- Dates run from 1970-01-01 to 2200-12-31, which keeps a year like 0202 or 9999 out of the log. A year mistyped inside that range, 2126 for 2026, still loads, and shows up as a span or a lapse of about a century.
- The merge is written out in queries 03, 04, and 05, once each, so each file runs on its own. A change to what counts as continuous cover has to be made in all three.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
