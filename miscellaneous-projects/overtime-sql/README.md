# Weekly Overtime Queries

Five SQLite queries that count overtime from a shift log under Nova Scotia's rule as it stands until April 2027: past 48 hours in a week, at one and a half times the regular wage, with no daily threshold. Each shift is split at 00:00 on Sunday, where the week starts, so a Saturday night's hours after midnight count in the week they are worked, and pay is worked out in whole cents from minutes rather than fractions of an hour. Counted shift by shift past eight hours, as if each shift were a day under a daily rule, the sample's overtime comes to 90:53 where the weekly rule owes 31:10.

## The rule these queries follow

Subsection 40(4) of Nova Scotia's [Labour Standards Code](https://nslegislature.ca/sites/default/files/legc/statutes/labour%20standards%20code.pdf) (R.S.N.S. 1989, c. 246) says an employee required to work more than 48 hours in a week is paid one and a half times their regular hourly wage for each hour past 48. The Code sets no overtime by the day, and neither does the [Minimum Wage Order (General)](https://novascotia.ca/just/regulations/regs/lscmwgen.htm) made under it.

The Code does not say which seven days make the week for this subsection. Section 9 of that order sets the order's own 48-hour week from Sunday to the following Saturday, or another seven-day period the employer sets as its customary pay period, and the province's overtime page takes any consistent seven-day period as the week. These queries use Sunday.

Section 2 of the [General Labour Standards Code Regulations](https://novascotia.ca/just/regulations/regs/lscgenls.htm) takes several groups out of subsection 40(4), among them supervisors and managers, people employed in a confidential capacity, information technology professionals, the transport industry, employees under a collective agreement, shipbuilding, ship repair and oil and gas work other than retail, primary processing in agriculture, Christmas trees and fishing other than meat processing, and employees covered by the minimum wage orders for construction and property maintenance or logging and forestry. Some of them are owed overtime under other rules instead: section 10 of the Minimum Wage Order (General) pays one and a half times the minimum rate past 48 hours, and past 96 hours in two consecutive weeks in the transport industry. The province's [overtime page](https://novascotia.ca/lae/employmentrights/overtime.asp) lists which group falls under which order.

The queries apply subsection 40(4) to every employee in the log and nothing else. The texts were checked in September 2026: the Code as consolidated to January 1, 2025, the order as amended to N.S. Reg. 266/2025 and the regulations as amended to N.S. Reg. 35/2025. The rule is simplified here, and none of this is legal or payroll advice.

The rule is about to change. An amending Act assented to on September 18, 2026 ([S.N.S. 2026, c. 17](https://nslegislature.ca/legislative-business/bills-statutes/bills/assembly-65-session-1/bill-256), section 4) amends subsection 40(4) from April 1, 2027: overtime starts past 44 hours, and the subsection applies where an employee is permitted to work those hours as well as where they are required to. Every week in the sample falls before that date, and the Act does not touch the minimum wage order or the regulations.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-log-shape.sql` | The log at a glance: shifts, employees, first start and last end, the weeks it runs across, and how many shifts run overnight or into the next week, with the split days and total time worked. |
| `sql/02-per-shift-overtime.sql` | Overtime counted shift by shift past eight hours, and the 48-hour rule applied to hours grouped by the week each shift starts in. |
| `sql/03-weekly-overtime.sql` | Each employee's minutes in each week with shifts split at 00:00 on Sunday, the time carried over from a Saturday night, regular time, overtime, and the minute overtime starts. |
| `sql/04-weekly-pay.sql` | Regular and overtime pay for each employee's week in whole cents, with a total line. |
| `sql/05-rules-side-by-side.sql` | The three counts of overtime week by week, the right pay, and how far each quick count would pay over or short. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.25 or newer for window functions.

```
cd miscellaneous-projects/overtime-sql
python run.py
```

That prints all five reports against the sample log. The test run checks the queries and the loader against hand-computed answers:

```
python run.py --test
```

Nineteen checks run. Six on the sample cover the log's shape, the per-shift and start-week counts, every week's minutes and overtime, every week's pay with its total, and the three counts side by side. The sixth prints all five reports and checks their column names, a rule as wide as each column, how many rows each prints and the first of them, the blank cells on the total lines, and that a query file that fails, has no query result, is not UTF-8 or is gone by the time it is read, or a folder named like one, stops them with a one-line message.

Six more run on logs built for the suite. The first has a week of exactly 48:00 and then a one-minute shift, whose overtime starts at that shift's first minute, a shift ending at exactly 00:00 on Sunday next to one starting then, and a 24-hour shift split 18:00 and 6:00. The second has a week that runs across New Year and reaches overtime, a Saturday night ending on New Year's Day, and a log whose last shift ends at exactly 00:00 on Sunday, which must not reach the week after. The third is Saturday nights only, where the right count runs a week past the last start, a week that takes in one Saturday night and sends out the next counts 8:00 carried in, and the start-week count pays the first week too much and the last too little while its total gap comes to nothing.

The fourth puts pay just under half a cent and on exactly half a cent, in regular pay and in overtime pay, so each has to round down and up in the right places. The fifth stores the sample in the opposite order in a table with no key and gets the same five reports. The sixth runs 20000 shifts of 24 hours at 999.99, each crossing into the next week, the most the loader allows, inside the step budget, beside a query that would run for ever, which the step budget stops, and a query of about 950 thousand steps, which a budget of 500 thousand stops and one of 2000 thousand lets finish.

Seven exercise the loader and the command line. They refuse the included bad log and overlapping shifts for one employee, naming both rows, in either order and when repeated, while shifts that touch load. They refuse starts and ends alike written with a T, seconds, 24:00, a day the month does not have, a missing leading zero, a doubled space, outside 1970 to 2200, blank, day first, with a zone, in fullwidth digits or without a time, a shift that ends when it starts or before, and one over 24 hours, next to a one-minute shift, one of exactly 24 hours, a leap day and both ends of the range, which load. They refuse employee codes in lower case, with a space, a doubled or outer hyphen, an accent, too long or blank, wages written fifteen wrong ways from 17.5 to Arabic-Indic digits, and a second wage for the same employee.

They count rows past blank lines, name a stray quote by its own row, refuse rows with too many or too few fields, a tab, text after a closing quote, a quote left open, a field past the parser's limit and a bad, renamed or reordered header, and cut a long value short in the message. They refuse an empty file, one with only a header, one that is not UTF-8 from its first line or only far down, a folder, a read that gives way partway and a line past 1000000 characters, while a byte-order mark and spaces around unquoted fields load. They stop a log past 20000 shifts as it is read and load one of exactly 20000.

On the command line they refuse a missing file, a name with a wildcard in it and a test run on any file other than the sample, and check that output and messages go out as UTF-8. The run ends with `all checks passed`.

The loader validates the log before any query runs. Point it at the included bad log to see a rejection:

```
python run.py --shifts data/invalid-shifts.csv
```

It stops at the first problem it reaches, naming the row where it has one. A byte that is not UTF-8 is one exception: the file is decoded about 8 KB at a time, so a bad byte can be reported first, without a row, when the problem sits on the bad byte's own line or on a line above it that ends in the same stretch of the file, or in a lone carriage return on the last byte of the stretch before. Overlapping shifts are another: they are checked once every row has been read, in order of employee and start, so a problem found row by row, or a bad byte anywhere in the file, is reported ahead of them. On the included bad log:

```
invalid-shifts.csv row 75: the shift from 2026-09-12 06:30 to 2026-09-21 13:40 runs 223:10; a shift runs at most 24:00
```

## Where counting by the shift goes wrong

Query 02 takes each shift whole into the week it starts in and counts anything past eight hours in it as overtime, as if each shift were a day under a daily rule. [British Columbia](https://www.bclaws.gov.bc.ca/civix/document/id/complete/statreg/00_96113_01), for one, pays overtime past eight hours a day, and a payroll set up that way pays for long shifts in weeks that never reach 48 hours. In her first week AMARA bakes five overnight shifts of 9:30, 47:30 in all: the per-shift count finds 7:30 of overtime, and Nova Scotia owes none. Across the log it finds 58:22 of overtime in ten weeks that owe nothing.

It misses the other way on short shifts. CELINE works split days at the counter, 06:30 to 10:30 and 14:00 to 17:45, seven days in the first week. No shift comes near eight hours, so the per-shift count finds nothing, but the week comes to 54:15 and owes 6:15. Her Labour Day week of seven 7:10 days, 50:10, owes 2:10 that the per-shift count misses as well.

Where either count finds overtime, the two agree only on DESMOND's week of six 10:20 days, at 14:00. Six shifts over eight hours each put six times eight, 48 hours, below the line, which is where the weekly rule puts it. Query 05 prices the difference: the per-shift count pays 976.56 too much across twelve weeks and 337.55 too little across four, 639.01 over on balance.

## Where the week boundary goes wrong

BRODIE's Saturday night shift runs from 21:00 on August 29 to 07:00 the next morning, 3:00 before midnight and 7:00 after. Counted whole in the week it starts in, that week comes to 55:00 with 7:00 of overtime, and the next to 43:00 with none. Split at 00:00 on Sunday, the first week is exactly 48:00, which owes nothing, and the second is 50:00, which owes 2:00.

The start-week count pays 208.95 too much in one week and 159.20 too little in the next. The 49.75 left over is the premium on the 5:00 of overtime it pays that is not owed. Overtime is owed by the week, so the week the hours land in changes the amount, not just the date it is paid.

DESMOND's last shift, from 22:00 on September 26 to 06:30 on the 27th, moves 6:30 into the week before under the same count, 130.98 paid a week early. Neither week passes 48 hours, so no overtime changes, but the week of September 27 only exists in the right count.

## Counting the week

Query 03 finds each shift's week with `date(starts, '-6 days', 'weekday 0')`, which steps back six days and forward to a Sunday, staying put if it is already on one, landing on the Sunday on or before the start. Times become whole minutes through `strftime('%s')`. A shift still going at 00:00 the next Sunday is cut there by crossing it with two rows, part 0 up to the boundary and part 1 after it, and part 1 only exists when the shift runs past. A shift runs at most 24 hours, so one cut is enough.

A running total of minutes in start order, within each employee's week, finds the minute overtime starts: the shift where the total passes 2880, and how far into it that happens. BRODIE's second week starts with the 7:00 carried over from Saturday night, and his overtime begins at 12:36 on Friday.

## Pay in whole cents

A wage is stored in cents and time in minutes. Regular pay is minutes times cents divided by 60, and overtime pay is minutes times cents times 3 divided by 120, which is the one and a half times, each rounded half up by adding half the divisor before the whole-number division. AMARA's 6:44 of overtime at 22.45 comes to 22674.5 cents and rounds up to 226.75. As hours, 6:44 is 6.7333 and so on, which no float holds exactly.

In a week with overtime, regular pay is 48 times the wage and always comes out even, so only the overtime line ever needs rounding. The sample's pay comes to 19569.98, 941.77 of it overtime.

## Sample data

A fictional bakery-cafe's shift log, 127 shifts by 5 employees from 06:30 on Sunday August 23, 2026 to 06:30 on Sunday September 27, one row per shift, listed by start: `shifts.csv`. AMARA bakes overnight, BRODIE bakes and works one Saturday night into Sunday, CELINE works split days at the counter, DESMOND preps in the early morning and ends the log with a Saturday night, and ELSPETH works part time, mostly on Saturdays. Labour Day, Monday September 7, falls in the third week: AMARA's Sunday night shift runs into its morning, and CELINE and ELSPETH work it.

The sample puts weeks on these boundaries: DESMOND at exactly 48:00 and then 48:01, CELINE at exactly 48:00 over twelve split shifts, a shift ending at exactly 00:00 on one Sunday and another starting at 00:00 on a later one. Pay lands on exactly half a cent in six weeks, five times in regular pay and once in overtime pay.

## Known limits

- The rule is simplified, and this is not legal or payroll advice. Every employee is taken to be covered by subsection 40(4); the groups the regulations take out of it, overtime at one and a half times the minimum rate, the transport industry's two-week count, averaging agreements and collective agreements are not modelled.
- Holiday pay is left out. Sections 40 to 42 of the Code pay for a general holiday and set a premium for working on one, on conditions the log does not hold, such as having received or being owed pay for at least 15 of the 30 calendar days before it. Hours worked on Labour Day count toward the week's 48 like any other hours, and the queries do not settle how the holiday premium and weekly overtime combine on the same hours.
- The week starts on Sunday, written as `'weekday 0'` in every query. An employer whose pay week starts on another day has to change each copy.
- The 48-hour line is written as 2880 minutes in queries 02 to 05, and one value holds for every week in a log. The amended subsection puts it at 44 hours from April 1, 2027, a Thursday, so a week that starts on or after April 4 needs 2640 in each copy, and the Act does not say how to count the week of March 28 that runs across the change. The queries count every logged minute of a week, while until then the subsection applies where an employee is required to work more than 48 hours, and the log cannot show whether more than 48 were required.
- Times are local clock times with no offset, so a shift across a change to or from daylight saving time is counted an hour off.
- Every minute between a shift's start and its end counts as worked. An unpaid meal break has to be logged as the gap between two shifts.
- Each employee has one wage for the whole log. A raise partway through means splitting the log at the raise.
- The first and last weeks hold only what the log holds: a shift that started before the log begins is missing from the first week, and the week of September 27 has only DESMOND's carried-over hours.
- A shift runs at most 24 hours, times run from 1970 to 2200, wages from 0.01 to 999.99, and a log holds at most 20000 shifts. A line holds at most 1000000 characters and a field at most 131072, the CSV parser's limit. A file is decoded in blocks of about 8 KB, so a byte that is not UTF-8 can be reported ahead of a problem on its own row or on an earlier row that ends in the same block, or in a lone carriage return on the last byte of the block before, and it is always reported ahead of overlapping shifts, which are checked once the whole file is read.
- A query that runs past 100000 thousand SQLite steps is stopped with an error. The costliest log found within the limits takes under a fifth of that, on 3.31 and 3.34 as much as on 3.50.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
