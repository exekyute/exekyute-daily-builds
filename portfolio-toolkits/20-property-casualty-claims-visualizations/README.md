# Property and Casualty Claims Visualizations

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a property and casualty claims analyst does, while
strengthening my foundational software development skills.

The repository holds three connected browser tools that follow a claims book from the
register through to reserving. The first reads a claims valuation register and writes a
clean claims file; the other two read that file, so the three rest on one source and tie
out to the cent. Each tool is self-contained and rule-based, with the rules written out
in its own `spec.md`. They are plain HTML, CSS, and TypeScript compiled to JavaScript,
so each one opens by double-clicking its `index.html`, with no framework, no build step,
and no server, and every file you load stays on your machine. Amounts are in Canadian
dollars, and all sample data is synthetic.

## The tools

1. **[Claims Aging and Status Funnel](01-claims-aging-funnel/)** rolls each claim up to
   its latest valuation, buckets the open inventory by age, counts the open, pending, and
   closed mix, averages the days to close, and exports the clean claims file the other two
   tools read.
2. **[Loss Ratio Dashboard](02-loss-ratio-dashboard/)** reads the clean claims file and
   shows the loss ratio, incurred losses over earned premium, for every line of business
   and accident year, with line, year, and overall totals.
3. **[Reserve Development Triangle](03-reserve-development-triangle/)** reads the clean
   claims file, pivots cumulative paid losses into a development triangle, reads the
   development factors, and projects each accident year's ultimate paid and outstanding
   reserve.

## How they connect

The Claims Aging and Status Funnel exports `clean-claims.csv`, one row per claim per
valuation point. The Loss Ratio Dashboard reads each claim's latest row; the Reserve
Development Triangle reads every row. The same sample runs through all three: incurred at
the latest valuation totals CAD 119,500.00, the figure the dashboard divides by premium,
and paid to date totals CAD 73,500.00, the figure the triangle develops to ultimate. Each
tool folder carries its own `sample-clean-claims.csv` so it also runs on its own.

## Running the tools

Open the tool's `index.html` by double-clicking it, then load the sample CSV in its
folder. Open `tests.html` the same way to see its checks print PASS or FAIL. Each
folder's README has the details and a worked example in its `spec.md`.

## Repository layout

```
property-casualty-claims-visualizations/
  LICENSE
  README.md
  01-claims-aging-funnel/
  02-loss-ratio-dashboard/
  03-reserve-development-triangle/
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
