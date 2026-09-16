# Business-Day Queries

Five SQLite queries about a support desk and its three-business-day target, on a calendar that knows which days the desk is open. The clock most people write first counts days off the wall calendar, which puts four of the sample's ten targets on days the desk is shut and marks two tickets missed that were answered with a day to spare. Numbering the open days in a calendar built by a recursive CTE turns both questions the desk asks into arithmetic: the business days between two dates is one number minus the other, and three business days after a date is the day whose number is three higher.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-ticket-log-shape.sql` | The log at a glance: tickets, how many are answered, how many are still waiting, the dates they were opened between, the last answer, and the size of the holiday list. |
| `sql/02-calendar-days.sql` | The clock on the wall calendar, and whether the desk is even open on the due dates it works out. |
| `sql/03-business-calendar.sql` | The calendar the counting rests on, built the same way in queries 04 and 05: every day, whether the desk is open, and a running number of the open ones. |
| `sql/04-business-due.sql` | The three-day target counted in business days: due date, age, and verdict for each ticket. |
| `sql/05-arrival-rule.sql` | The same with the desk's arrival rule, where a ticket that lands on a closed day starts on the next open one. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.25 or newer for window functions.

```
cd miscellaneous-projects/business-days-sql
python run.py
```

That prints all five reports against the sample files. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Twenty checks run. Nine on the sample cover the log's shape and holiday count, the four due dates the calendar clock puts on closed days, its verdicts, the size of the business calendar and its total of open days, the numbering standing still over a weekend and a holiday, every business-day due date and verdict, the two tickets the clocks disagree on, the two that arrived on closed days, and the one that turns from missed to met when the clock starts on the next open day. Six on desks built for the suite cover an answer logged on a Saturday, a target set the day before a five-day closure, a ticket that arrives on a holiday, an on-call answer logged before its clock starts, a desk that opens one day a week, and an answer that lands long after the calendar's 30-day margin. Five exercise the loader: an answer dated before its ticket was opened; row numbers past blank lines and a stray quote, along with text after a closing quote, a repeated ticket_id, and a date written without its leading zeroes; a control character, rows with too many or too few fields, a renamed header, a date outside the range the log can use, and a file with only a header, next to a byte-order mark it reads through; a holiday listed twice, one with no name, one that is not a real date, and a good list that loads; and the limit on closed days, which takes six in a row and turns away seven. The run ends with `all checks passed`.

The sample holiday list is used for any ticket log unless `--holidays` names another, since a holiday list belongs to the desk rather than to one file of tickets. The loader validates both CSVs before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --tickets data/invalid-tickets.csv
```

It stops at the first problem, naming the row when the problem is in one: `invalid-tickets.csv row 4: ticket 1003 was answered on 2026-09-01, before it was opened on 2026-09-04`. An answer dated before its ticket would make the age of the ticket negative and put its answer before its own due date, so the loader refuses it.

## The clock on the wall calendar

Query 02 adds three days to the opening date and takes the age of a ticket as the difference between two `julianday` numbers, which counts Saturdays, Sundays, and holidays like any other day. Two things go wrong. Four of the ten targets land on a day the desk is shut: ticket 1002 is due on a Sunday, 1003 on Labour Day, and the query says so in its `desk_on_due` column. And because the count runs over the closed days, tickets 1002 and 1003 read as five days old when the desk had been open for two, so both come back missed.

## Numbering the open days

Query 03 builds the calendar it needs, and queries 04 and 05 build the same one again. A recursive CTE walks a day at a time from the first ticket to thirty days past the last one, or to the last answer if that falls further out, far enough that every due date has a day to land on. A day is open unless it falls on a weekend or in the holidays table, and a running `SUM` over that flag numbers the open days: `business_no` is how many days the desk has been open up to and including this one. A closed day keeps the number of the open day before it, so the count stands still across Saturday, Sunday, and Labour Day, reading 5 on Friday September 4 and 5 again on Monday September 7, then 6 on Tuesday September 8.

## Counting the target

Query 04 rebuilds that calendar and joins each ticket to it on the day it was opened and on the day it was answered, then subtracts one number from the other. The due date comes from the same numbering, by joining back to the open day whose number is three higher, so a due date is always a day the desk is open. Tickets 1002 and 1003 come out two business days old and met, where the wall calendar called them missed. Ticket 1005 is still missed at four business days, and 1009 at six. A ticket answered the day it arrived comes to 0, and one still waiting has no answer to join to, so its age is blank and its verdict is open.

## Which day the clock starts

Query 05 adds the rule the desk works to: a ticket that arrives on a closed day starts its clock on the next open day. In the numbering that is one line of arithmetic, since a closed day already carries the number of the open day before it: add 1 on a closed day and 0 on an open one. Ticket 1004 arrived on Saturday September 5 and starts on Tuesday September 8, the Monday being Labour Day, which moves its target from September 10 to September 11. It was answered on September 11, so the ticket query 04 called missed at four business days is met at three. Ticket 1007 arrived on a Sunday and shifts a day as well, from a target of September 16 to September 17, and was met either way.

## Sample data

Ten tickets at a fictional support desk, opened between Monday, August 31 and Friday, September 18, 2026, one of them still waiting. Two arrive on a weekend, one is answered the day it arrived, and one is answered eight calendar days later. The holiday list holds the two days this desk closed in the period the calendar covers: Labour Day on Monday, September 7 and Thanksgiving on Monday, October 12. The ticket file is deliberately not in date order.

## Known limits

- The target is three business days, written into queries 02, 04, and 05. Tickets with different targets by priority need the target as a column on the ticket and the joins to read it.
- Dates only, with no times. A ticket opened at 4:55 in the afternoon and one opened at 9 in the morning the same day get the same clock, and a desk that answers in hours needs timestamps and opening hours instead.
- An answer logged on a closed day counts as the last open day before it, since that is the number the calendar carries there. A Saturday answer reads as the Friday, and one logged on any closed day before the clock in query 05 starts counts as 0 rather than as a day below zero.
- The calendar runs 30 days past the last ticket, or to the last answer if that is later, and the loader refuses a holiday list that shuts the desk for seven days or more in a row anywhere a due date could land, which is the case that could push one past the end of it. Closures further out are left alone, since every due date comes from an opening date.
- Dates run from 1970-01-01 to 2200-12-31. A date outside that is refused, which keeps a mistyped year or a 9999 sentinel from building a calendar of millions of days.
- Weekends are Saturday and Sunday. A desk that opens on Saturdays, or one on a different week altogether, needs the open-day test changed.
- The holiday list is the desk's own, not a statutory list. Nothing checks it against one, and the sample's two days are the ones this desk closed.
- What counts as a closed day is written out five times: once in query 02 for its due date, once in each of queries 03 to 05, and once in the loader's check on the holiday list. A change to it has to be made in all five.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
