# Municipal 311 SQL Analytics

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a municipal 311 service-request analyst does,
cleaning request records and reporting on backlog, resolution time, and service
levels, while strengthening my foundational software development skills.

The toolkit is four tools wired into one pipeline around SQLite. Three SQL tools clean
the raw requests, roll the backlog forward month by month, and measure resolution time
against target; a browser dashboard reads what they write and lays it out. Each tool is
self-contained and rule-based, with the rules written out in its spec, and the whole
thing runs entirely on your machine with no framework, no build step, and no server.
All sample data is synthetic.

## The tools

1. **[Intake and Data Quality](01-intake-and-data-quality/)** is SQLite with a Python
   runner. It flags duplicate ids, missing fields, impossible dates, and status
   mismatches in the raw requests, then writes the clean rows for the rest of the
   pipeline.
2. **[Backlog and Flow](02-backlog-and-flow/)** is SQLite with a Python runner. It rolls
   the clean requests forward per department and month (opening plus new minus closed
   equals closing) and totals the cost to serve what was closed, in Canadian dollars.
3. **[SLA and Aging](03-sla-and-aging/)** is SQLite with a Python runner. It measures
   time to close against category targets for resolved requests and ages the open
   backlog by days waiting.
4. **[Operations Dashboard](04-operations-dashboard/)** is a browser tool. It reads the
   CSVs from the SQL tools and shows the backlog and flow, the open requests by age, and
   time to close, re-deriving the totals so they match the SQL runners.

## How they connect

The intake tool writes `clean_requests.csv`. The backlog and SLA tools read it and write
`period-summary.csv`, `sla-aging.csv`, and `category-sla.csv`. The dashboard reads those
and re-derives the totals. A worked example runs end to end: Roads in 2025-01 opens at 2,
adds 4, closes 3, and closes the month at 3, with a cost to serve of $256.50; across
every department and month the cost to serve totals $708.50, the overall time to close is
11.22 days, and five requests are open with four overdue. The SQL runners assert these
and the dashboard re-derives them, so the two agree to the cent.

## Running the tools

The three SQL tools run with Python 3 (standard library only) from their folders, in
order: intake first, then backlog and SLA, which read the clean file it writes. The
Operations Dashboard opens by double-clicking its HTML file and loading the three CSVs.
Each tool folder has its own README with the exact commands and a `spec.md` covering
purpose, inputs, validation, logic, outputs, and edge cases.

## Repository layout

```
municipal-311-sql-analytics/
  LICENSE
  README.md
  01-intake-and-data-quality/    SQL (SQLite) + Python runner
  02-backlog-and-flow/           SQL (SQLite) + Python runner
  03-sla-and-aging/              SQL (SQLite) + Python runner
  04-operations-dashboard/       browser
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
