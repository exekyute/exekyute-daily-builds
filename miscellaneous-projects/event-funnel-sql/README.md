# Event Funnel Queries

Five SQLite queries that turn a raw product event log into an ordered signup-to-purchase funnel: who reached each stage, where the drop-offs happen, how long each step takes, and which users a naive count gets wrong. The ordering is the whole point: a stage only counts when it happens at or after the stage before it, so a user who bought before creating a project is a stage-two drop-off, not a conversion. On the sample log, raw events show 5 purchases and the ordered funnel finds 3.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-event-counts.sql` | The raw shape of the log: fires and distinct users per event, funnel or not. |
| `sql/02-ordered-funnel.sql` | One row per entrant with the timestamp they reached each stage, NULLs from their exit stage on. |
| `sql/03-naive-vs-ordered.sql` | Every user's furthest stage counted both ways, with a note naming each disagreement. |
| `sql/04-stage-gaps.sql` | Hours between consecutive stages, with a median per transition. |
| `sql/05-funnel-summary.sql` | The funnel itself: users per stage, share of signups, conversion from the stage before. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/event-funnel-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against hand-counted answers:

```
python run.py --test
```

Eight checks cover the raw counts, the entrant list, the same-minute boundary, the out-of-order purchase, both naive disagreements, the three medians, and the full summary, then print `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --events data/invalid-events.csv
```

It stops on the first problem and names the row: `invalid-events.csv row 3: user_id is empty`. The row after that has a timestamp without zero padding, which the loader would catch next.

## How the ordering works

The funnel is a chain of four CTEs. Stage one is each user's earliest signup. Every later stage is that user's earliest matching event at or after the stage before it, and the join to the previous stage means nobody reaches stage three without stage two. `LEFT JOIN`s stitch the chain back together so drop-offs stay visible with NULLs from their exit stage on.

Two details in the sample data prove the mechanics. Ana's first project landed in the same minute as her signup and still counts, because the comparison is at-or-after. She also fired `project_created` twice, and `MIN` keeps the first valid one, so repeats change nothing.

## What the naive count gets wrong

The comparison query counts each user's furthest stage two ways: naive asks only whether the event ever fired, ordered demands the sequence. Six of the eight users agree under both. The two who differ are the reason ordered funnels exist:

| user | naive says | ordered says | why |
| --- | --- | --- | --- |
| dee | purchased | project_created | She bought thirty minutes after signing up and created her project the next day, so no purchase follows her funnel path. |
| gus | purchased | nothing | He purchased without ever signing up, so he never entered the funnel at all. |

That gap is the difference between the 5 raw purchases and the 3 conversions the summary reports.

## Stage gaps

SQLite has no `PERCENTILE_CONT`, so the median transition time is the middle row by `ROW_NUMBER`, averaging the two middle rows when the count is even. On the sample: 13.25 hours from signup to first project, 34.50 to the teammate invite, 76.00 from invite to purchase. The invite step is also the funnel's weakest conversion at 66.7 percent, which is where a product conversation would start.

## Sample data

Eight fictional users and 24 events across August 1 to 12, 2026, including a stray `help_viewed` event the funnel ignores. The ordered funnel runs 7 signups, 6 projects, 4 invites, 3 purchases: 42.9 percent end to end.

## Known limits

- There is no conversion window. A purchase a year after the invite would still count; real funnels usually bound each step, which means one more date condition per CTE.
- The stage names and their order are written into the CTE chain, and the chain repeats in four files.
- Timestamps are minute-grained, so events inside the same minute count as in order regardless of their true sequence. Second-grained data would resolve it.
- Naive here means "the event ever fired". Analytics tools disagree on that definition, so their numbers will not necessarily match either column.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
