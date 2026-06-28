# Craft Brewery Cost Accounting Toolkit

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a craft brewery cost accountant does, costing
production from the purchase order through to gross margin and the month-end close,
while strengthening my foundational software development skills.

The toolkit is seven tools wired into one pipeline. Each writes a file the next one
reads, so a single period of brewery data flows from raw purchases all the way to a
visual dashboard. Each tool is self-contained and rule-based, with the rules written
out in its spec. The command-line tools are Python using the standard library only,
the month-end close is SQL on SQLite with a small Python runner, and the dashboard is
plain HTML, CSS, and vanilla JavaScript. There is no framework, no build step, and no
server, and everything runs on your machine. Money is carried as decimal values and
integer cents, rounded half up to the cent throughout, so the figures agree across
every tool. All sample data is synthetic.

## The tools

1. **[Procurement Landed Cost](01-procurement-landed-cost/)** is command-line Python.
   It folds freight and Canadian import duty into the landed cost of malt, hops, cans,
   kegs, and labels, spreading freight across an order by value with the
   largest-remainder method. It writes `landed_costs.csv`.
2. **[Batch Production Costing](02-batch-production-costing/)** is command-line Python.
   It rolls materials, packaging, labour, and overhead into each brew batch, absorbs
   yield loss into the good beer, and costs every finished can and keg. It writes
   `batch_costs.csv` and `finished_unit_costs.csv`.
3. **[Perpetual Inventory Valuation](03-perpetual-inventory-valuation/)** is
   command-line Python. It keeps a perpetual weighted-average ledger across raw
   material, work in process, and finished goods, and flags an over-issue rather than
   hiding it. It writes `perpetual_valuation.csv`.
4. **[Excise Duty Engine](04-excise-duty-engine/)** is command-line Python. It computes
   federal beer excise on packaged volume using the CRA reduced-rate brackets by ABV
   class. It writes `excise_summary.csv`.
5. **[COGS and SKU Profitability](05-cogs-sku-profitability/)** is command-line Python.
   It combines production cost and excise into a per-SKU cost of goods sold and reports
   gross margin by product line and channel. It writes `sku_margins.csv`.
6. **[Month-End Close](06-month-end-close/)** is SQLite with a Python runner. It
   reconciles the book inventory against the physical count, flags variances over
   tolerance, generates the closing journal entries, and proves the trial balance
   balances.
7. **[Cost Dashboard](07-cost-dashboard/)** is a browser tool. It reads the pipeline
   CSVs and draws the period close on one page: inventory valuation by category, a
   batch cost waterfall, excise by ABV class, month-end variances, and SKU margins.

## How they connect

Each tool consumes what the tool before it wrote. The proof that they agree is a single
period costed two ways. The perpetual valuation ends the month at 17,240.79 of
inventory; the SQL month-end close, reading that file and reconciling it against the
physical count, reports the same 17,240.79 and a trial balance that balances at
31,168.36. The excise engine computes 149.17 of federal duty, and the close books the
same 149.17. The browser dashboard, reading the same CSVs independently, shows the same
inventory total, the same excise, the 6,355.99 batch cost, and the two count
exceptions. Each Python tool ships a unittest suite, the close ships a runner that
asserts its totals and prints PASS or FAIL, and the dashboard ships a tests.html page,
so every figure can be reproduced. The excise rates used are the CRA rates of duty on
beer brewed in Canada, per hectolitre, effective April 1, 2026, written into the engine
with a dated note.

## Running the tools

Tools 1 through 5 run with Python 3 (standard library only) from their own folders.
The month-end close runs through its standard-library Python runner against the SQLite
schema. The dashboard opens by double-clicking its HTML file. Each tool folder has its
own README with the exact commands and a `spec.md` covering purpose, inputs, validation,
logic, outputs, and edge cases, plus screenshots of it in action. Every tool also
accepts a deliberately invalid sample so you can see it reject bad input.

## Repository layout

```
craft-brewery-cost-accounting-toolkit/
  LICENSE
  README.md
  01-procurement-landed-cost/        Python
  02-batch-production-costing/        Python
  03-perpetual-inventory-valuation/   Python
  04-excise-duty-engine/              Python
  05-cogs-sku-profitability/          Python
  06-month-end-close/                 SQL (SQLite) + Python runner
  07-cost-dashboard/                  browser
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
