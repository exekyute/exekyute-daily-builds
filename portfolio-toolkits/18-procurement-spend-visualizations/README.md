# Procurement Spend Visualizations

A personal project, one of several I build to model real-world job descriptions and turn them
into working business utilities. The goal is to practice applied problem-solving on the kind of
work a procurement and spend analyst does, while strengthening my foundational software
development skills.

The repo holds three browser visualizations that read one shared spend dataset. The Spend
Analysis Dashboard validates and totals the raw spend lines and exports a normalized CSV. The
Supplier Pareto and Savings Tracker and the PO/Invoice Compliance view both read that same
exported file, so the three tell one story from the same numbers. Each view is deterministic and
rule-based, with the rules written out in its own spec. They are plain HTML, CSS, and JavaScript
compiled from TypeScript, with no framework, no build step, and no server. Each opens by
double-clicking its HTML file, and everything stays on your machine.

## The tools
1. **[Spend Analysis Dashboard](01-spend-analysis-dashboard)** - validates raw spend lines, totals
   spend by category and supplier, and exports the normalized CSV the other two read.
2. **[Supplier Pareto and Savings Tracker](02-supplier-pareto-savings)** - ranks suppliers and
   marks the vital few at the 80 percent cut, and tracks realized savings against target.
3. **[PO/Invoice Compliance](03-po-invoice-compliance)** - flags off-contract spend and three-way-
   match exceptions where the purchase order, receipt, and invoice do not agree within tolerance.

## How they connect
The Spend Analysis Dashboard is the producer. Load the raw spend lines, then export
`normalized-spend.csv`. Both other views read that file, so the supplier totals in the Pareto and
the line amounts in the compliance view match the dashboard to the cent. Each tool ships with a
copy of the sample so it can also be run on its own.

## Running it
Each tool folder has its own README with copy-paste steps. In short: open a tool's `index.html`,
load the sample CSV, and the charts and tables fill in. Open `tests.html` in any tool to run its
checks and see them pass. The compiled JavaScript is committed, so nothing needs building to run
the tools. To rebuild after editing the TypeScript under a tool's `src/`, run `npx -p typescript tsc`
in that tool folder (Node and TypeScript installed).

## License
MIT, copyright Kevin Yu (github.com/exekyute).
