# MRR Bridge Queries

Five SQLite queries that explain each month's change in monthly recurring revenue (MRR). From a log of what each customer paid each month, they split the move from opening to closing MRR into new customers, customers coming back, expansion, contraction and churn, check that the pieces add up, and turn them into gross and net revenue retention. The log has no row for a month a customer did not pay, so queries 03 to 05 first give every customer a row in every month; built with LAG over the rows as they stand, the same bridge never records a churn and leaves money unexplained in eight of the eleven months the sample's bridge covers.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-log-shape.sql` | The log at a glance: the months it covers, the customers and rows, and the months customers skipped between their first payment and their last. |
| `sql/02-lag-by-row.sql` | The bridge built with LAG over the rows the log holds, and how much of each month's change it leaves unexplained. |
| `sql/03-movements.sql` | Every customer's change from one month to the next, named as new, reactivation, expansion, contraction or churn. |
| `sql/04-bridge.sql` | Each month's opening MRR, the five movements and closing MRR, a check that they add up, and a total line for the whole log. |
| `sql/05-retention.sql` | Customers paying at open, lost, won and paying at close, with gross and net revenue retention for each month. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.25 or newer for window functions.

```
cd miscellaneous-projects/mrr-bridge-sql
python run.py
```

That prints all five reports against the sample log. The test run checks the queries and the loader against hand-computed answers:

```
python run.py --test
```

Eighteen checks run. Six on the sample cover the log's shape, the LAG bridge and what it leaves unexplained, every customer's movement, the monthly bridge with its total line, and customers and retention by month. The sixth prints all five reports and checks their column names, a rule as wide as each column, how many rows each prints and the first of them, and that a query file that fails, has no query result, is not UTF-8 or is gone by the time it is read, or a folder named like one, stops them with a one-line message.

Four more run on logs built for the suite. The first has a month nobody paid for at the turn of a year, which still gets its row, a customer seen only in the first month who comes back as a reactivation, a month with no change, and a month that opens with nobody paying, whose rates are left blank in the printed report too. The second puts rates on an exact half, which have to round up where rounding half to even would round down and printf or ROUND on a float changes with the SQLite version. The third stores the sample in the opposite order in a table with no key and gets the same five reports, and the fourth runs 36 customers from 1970-01 to 2200-12, each changing every month after the first, near the most customer-months the loader allows, inside the step budget, beside totals from the largest amounts, which print to the cent, and a query that would run for ever, which the step budget stops.

Eight exercise the loader and the command line. They refuse a customer listed twice in a month; months past 12, at 00, without a leading zero or with a two-digit year, with a slash, a day, a month name or fullwidth digits, blank, or outside 1970 to 2200; customer codes in lower case, with a space, a doubled or outer hyphen, an accent or fullwidth letters, too long or blank; and amounts of 0.00, negative, whole, with one or three decimal places, zero-padded, with seven digits before the point, in exponent form, blank, with a comma, a dollar sign or no digit before the point, or with Arabic-Indic digits in them, next to the edge values that load. They count rows past blank lines and a line of spaces, name a stray quote by its own row, in a data row or in the header, refuse rows with too many or too few fields, a line of commas, a tab, text after a closing quote, a quote left open, a field past the parser's limit and a bad, renamed or reordered header, also one written as a single quoted field or with a trailing comma, and cut a long value or header short in the message.

They also refuse an empty file, one of blank lines, one with only a header, one that is not UTF-8 from its first line or only far down, or holds only part of a byte-order mark, a folder, a read that gives way partway and a line past 1000000 characters, while a byte-order mark, blank lines before the header and spaces around unquoted fields, in the header as well, load. They refuse a log of one month or of more than 100000 customer-months, stop one past 100000 rows as it is read, before a bad byte further down, and load one of exactly 100000 customer-months. On the command line they refuse a missing file, a name with a wildcard in it and a test run on any file other than the sample, and check that output and messages go out as UTF-8. The run ends with `all checks passed`.

The loader validates the log before any query runs. Point it at the included bad log to see a rejection:

```
python run.py --mrr data/invalid-mrr.csv
```

It stops at the first problem it reaches, naming the row where it has one:

```
invalid-mrr.csv row 63: KEMPT-ROAD-CLINIC appears twice for 2025-07; one row per customer and month, with the amounts added together
```

## Why LAG over the rows falls short

Query 02 compares each row with the customer's row before it, the usual way to find a change. But the row before is not always last month. In June, DARTMOUTH-CHIRO comes back at 159.00 after three months away; LAG compares that with its 159.00 in February, sees no change, and books nothing. A customer who leaves has no row in the month they left, so no churn is ever recorded.

Opening and closing are the month totals and are right, so what the movements miss lands in the unexplained column. The -189.50 in April is NORTH-END-VET leaving. In October CITADEL-OPTICAL comes back at 149.00; LAG compares that with the 99.00 it paid in June, before it left, and books 50.00 of expansion, so 99.00 of the 149.00 goes unexplained.

June is the trap. ANNAPOLIS-EYE-CARE leaves with 159.00 and DARTMOUTH-CHIRO comes back with 159.00, LAG sees neither, and the unexplained column reads 0.00. A bridge that adds up has not been shown right. Booking the unexplained amount as churn only works in a month when nobody came back: in October and November it is positive, money arriving that no movement explains, and over the year the column sums to -512.50 against the 885.50 that actually left.

## The bridge

Query 03 gives every customer a row in every month of the log, at 0.00 where they paid nothing, by crossing the list of customers with a calendar built by a recursive CTE. The calendar counts months as the year times twelve plus the month counted from zero, so it runs across a new year and keeps a month in which nobody paid at all. With a row in every month, LAG finds last month every time.

A change from 0.00 is new, or a reactivation if the customer paid in any earlier month of the log, which a running MAX over the months before settles. A change to 0.00 is churn. Anything else is expansion or contraction.

Query 04 adds the movements up by month. Every change falls under exactly one of the five, so opening plus the movements always comes to closing. The sample year runs from 1790.25 to 2137.75 through 761.00 new, 407.00 back again, 200.00 of expansion, 135.00 of contraction and 885.50 of churn.

## Retention

Query 05 counts customers and rates each month. Gross revenue retention is the share of opening MRR still there after contraction and churn; net revenue retention adds expansion back. New customers and reactivations count in neither, since they were not paying when the month opened.

Net passes 100 percent in August, at 101.5, although MAPLE-LEAF-AUDIOLOGY left that month: HARBOUR-DENTAL's 100.00 of expansion outweighs the 75.00 MAPLE-LEAF-AUDIOLOGY took with it. Gross never can. The rates are worked out in whole numbers and rounded half up to a tenth of a percent. Held as a float, 90.05 percent sits just under the half: SQLite 3.50's printf prints it as 90.0 and 3.31 and 3.34 print 90.1, so a rate held as a float would change with the SQLite version.

## Sample data

Fourteen fictional customers of a software subscription, one row for each month a customer paid, January to December 2025: 107 rows, listed by month and customer. An amount is the customer's MRR for that month. Nine are paying in January. Five join during the year, three leave and come back, and four leave for good, for seven churns in all.

## Known limits

- A customer is new the first time they start paying after the log's first month; anyone paying in that first month is part of the opening. One who paid before the log starts but not in its first month reads as new, and one who comes back after years away is a reactivation however long the gap; counting a long-gone customer as new business would take one more condition.
- A month with no rows at all between the first month and the last is read as a month nobody paid, so a log exported with a month missing shows every customer paying on both sides of it churning and coming back.
- MRR is one figure per customer per month in one currency, from 0.01 to 999999.99. A change partway through a month, a credit or a one-off charge has to be settled into that figure before it reaches the log.
- Rates are for one month at a time. Multiplying them together does not give a yearly rate for the customers paying in January, since customers who join during the year are part of later months' openings.
- Months run from 1970-01 to 2200-12, a field holds at most 131072 characters (the CSV parser's limit) and a line at most 1000000, and the customers times the months in the log may come to at most 100000, since the queries give every customer a row in every month.
- A query that runs past 100000 thousand SQLite steps is stopped with an error. The costliest log found within the limits above takes about a quarter of that on SQLite 3.50, and about a third on 3.31 and 3.34.
- The calendar and the rules for naming a movement are written out in queries 03, 04 and 05, and the calendar in 02 as well, so each file runs on its own. A change to either has to be made in each copy.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
