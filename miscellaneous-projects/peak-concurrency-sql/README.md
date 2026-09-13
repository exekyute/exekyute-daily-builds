# Peak Concurrency Queries

Five SQLite queries on a help desk's call log, which records only when each call started and ended, built around one question: how many calls were live at once. Each call becomes a +1 and a -1, and a running `SUM` over them in time order gives the live count. The obvious first version reports six calls at the day's worst moment when there were five, and puts a caller on hold at 13:30 while three agents were each on one call. Both come from how it breaks a tie between a call ending and another starting in the same minute.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-call-log-shape.sql` | The log at a glance: calls, first call, last hang-up, the minutes between them, and the minutes spent on calls. |
| `sql/02-naive-peak.sql` | The obvious first sweep, which counts a start before an end in the same minute. |
| `sql/03-timeline.sql` | The live count done right: every change, the count it changed to, and how long it held. |
| `sql/04-average-load.sql` | The average number of calls live, taken over the timeline's rows and over the clock. |
| `sql/05-over-capacity.sql` | The stretches with more calls live than three agents could take, and the caller-minutes on hold. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.25 or newer for window functions.

```
cd miscellaneous-projects/peak-concurrency-sql
python run.py
```

That prints all five reports against the sample log. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Eighteen checks run. Ten on the sample cover its row count and shape, the naive peak and the hold it invents, the true peak, the same-minute changes that drop out of the timeline, two calls arriving together, the timeline covering the whole span, the two averages, and both stretches over capacity. Six on logs built for the suite cover back-to-back calls, a dip to exactly three between two busy spells, a time-weighted average of 380 minutes over 120 that has to round to 3.17, two calls ending and one starting in the same minute inside a stretch, an average of exactly 1.005, and calls across midnight. Two run the loader on bad files. The run ends with `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --calls data/invalid-calls.csv
```

It stops on the first problem and names the row: `invalid-calls.csv row 18: call 111 ends at 2026-09-08 11:40, before it starts at 2026-09-08 12:06`. A call that ends before it starts puts its -1 ahead of its +1, which takes one call off the count for every minute between the two times, so the loader refuses it.

## The naive peak

Query 02 turns each call into two events and runs `SUM(delta)` over them in time order. In a minute where one call ends and another starts, the answer depends on the tiebreak, and query 02 takes the start first. At 10:25 call 104 hung up and call 108 came in; the query counts 108 before it lets 104 go, so for one step six calls are live, and that step is the day's peak by this count. The same thing happens at 13:30, when call 113 ended and call 115 began with three calls on the line: the query shows four for a step, a caller on hold that three agents never kept waiting.

The tiebreak is a statement about when a call leaves the line. This log records `ended_at` as the first minute the line was free: a call from 10:00 to 10:30 lasted 30 minutes, 10:00 through 10:29, which is what `ended_at` minus `started_at` says. Taking the start first keeps the call on the line at 10:30, a 31st minute its own length leaves out.

## The timeline done right

Query 03 nets the events in each minute before the running sum, with `GROUP BY event_time` and `SUM(delta)`, so a minute where one call ends and another starts nets to zero. `HAVING SUM(delta) <> 0` drops those minutes, since the count did not change in them, which is why neither 10:25 nor 13:30 appears in the timeline. `LEAD` gives each row the minute of the next change, so every row but the last is a count and how long it held: five calls live from 10:18 to 10:30, twelve minutes, the day's true peak. Two calls arriving in the same minute raise the count by two in a single row, as at 11:05, where it goes from 0 to 2.

Flipping query 02's tiebreak to take ends first also finds a peak of five here, but it passes through counts that last no time at all: at 10:25 it steps down to four before coming back to five. When two calls end and one starts in the same minute, a dip like that can reach three, and a timeline built from that sweep splits one stretch over capacity into two in query 05. One of the suite's built logs checks that the netted timeline keeps it whole.

## Averages, and time over capacity

Query 04 averages the live count two ways over the seven hours from 09:05 to 16:05, using the 34 timeline rows that have a length, every row but the closing hang-up. Their plain average is 1.74 calls; weighting each row by its minutes gives 1.25. The row average runs high because the morning rush changes every few minutes and fills the timeline with rows, while the 54-minute lull after 12:06, with no calls live, is a single row. The time-weighted figure also equals the day's 525 call minutes divided by its 420 minutes, since live times minutes summed over the timeline adds up every call's length, and the query works it both ways as a cross-check.

Query 05 finds the stretches with more than three calls live. A running count of the rows at three or fewer holds still across a run of rows over three, so it groups each run into one stretch. From 10:12 to 10:36 the desk was over capacity for 24 minutes, peaking at five calls, with 36 caller-minutes on hold; from 14:52 to 15:00 it was over for 8 minutes, with 8 caller-minutes on hold. Nothing appears at 13:30, where query 02 put a caller on hold.

## Sample data

Twenty calls to a fictional help desk with three agents on shift, logged on Tuesday, September 8, 2026, from 09:05 to 16:05. Times are to the minute, and the phone system records each call's `ended_at` as the first minute its line was free again. Twice a call ends in the same minute another starts, at 10:25 and 13:30; two calls arrive together at 11:05, and no call is live from 12:06 to 13:00. The file is deliberately not in time order.

## Known limits

- Queries 01 and 03 to 05 depend on `ended_at` being the first free minute, the way this log records it. A system that cuts both times down to the minute could log a real overlap, such as a call ending at 10:25:40 and another starting at 10:25:05, as the same pair of minutes, and queries 03 to 05 would count it as a clean handoff. Telling the two apart needs seconds, which the loader and the minute arithmetic would have to be changed to read.
- A call that starts and ends in the same minute is refused, since with `ended_at` as the first free minute it never held a line. A log with calls shorter than a minute needs them dropped or lengthened to a minute before loading.
- Times are read as clock times with no time zone. A call that runs across a daylight-saving change comes out an hour too long or too short, and one that crosses the autumn change can look as if it ends before it starts, which the loader refuses. Times in UTC avoid both.
- Three agents all day is written into queries 02 and 05. A desk whose staffing changes through the day needs a staffing table joined against the timeline.
- The log has no answer time, so it cannot tell a caller on hold from one talking to an agent. The hold figures assume an agent picks up as soon as one is free.
- Averages cover the span from the first call to the last hang-up. Open hours with no calls before 09:05 or after 16:05 are left out, and a log covering several days counts the closed hours overnight as time with no calls live.
- Queries 04 and 05 repeat query 03's timeline so that each file runs on its own. A change to how the timeline is built has to be made in all three.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
