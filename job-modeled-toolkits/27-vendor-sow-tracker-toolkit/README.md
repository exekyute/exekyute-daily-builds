# Vendor SOW Earned-Value Tracker

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a vendor or program manager does, tracking the
effort a supplier logs against a statement of work and the budget that backs it,
while strengthening my foundational software development skills.

This toolkit has two tools. A command-line Python engine walks the SOW week by week
and measures earned value against cost, producing a timeline with the cost
performance index, the estimate at completion, the variance, and the holdback. A
browser view plots that timeline as a burn chart against the budget, with per-week and
per-milestone tables. Each tool is self-contained and rule-based, with the rules
written out in its own `spec.md`, and there is no framework, no build step, and no
server. The sample data is synthetic, seeded so the SOW moves between on-track and
over-budget across its milestones.

## The tools
1. **[SOW engine](01-sow-engine/)** command-line Python that reads the milestones and
   the effort log and writes the earned-value timeline.
2. **[SOW timeline view](02-sow-timeline/)** a browser view that plots the timeline as
   a burn chart against the budget and lists each period and milestone.

## How they connect

The engine writes `timeline.csv` from the milestones and the effort log. The view
reads that file (a copy ships with it so it renders on its own) and draws the chart and
tables, recovering the budget from the earned value and percent complete. The shared
hand-check runs the whole way through: an 80,000 SOW that ends up costing 85,000, so
the estimate at completion is 85,000.00, the variance is -5,000.00, and the 8,000.00
holdback releases at completion. The engine's `unittest` suite and the view's
`tests.html` both confirm these numbers to the cent.

## Running the tools

Python 3 runs the engine. The view needs only a browser.

```
# 01 SOW engine
python -m unittest
python cli.py --holdback 0.10
```

Open `02-sow-timeline/index.html` in a browser for the view, and
`02-sow-timeline/tests.html` for its test page. Each tool folder has its own README and
`spec.md`.

## Repository layout
```
27-vendor-sow-tracker-toolkit/
  LICENSE
  README.md
  01-sow-engine/
  02-sow-timeline/
```

## License
Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
