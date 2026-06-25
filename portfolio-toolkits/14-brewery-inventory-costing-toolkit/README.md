# Brewery Inventory Costing Toolkit

A personal project, one of several I build to model real-world job descriptions
and turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a junior inventory accountant at a craft
brewery does, while strengthening my foundational software development skills.

The repo holds two tools that run in sequence. The costing engine keeps perpetual
weighted-average inventory and computes federal excise duty, writing a valuation
CSV and an excise summary CSV. The reconciliation tool reads those two files plus
a physical count sheet, reconciles book to count, flags variances over tolerance,
and rolls up closing value and duty for month-end. Both are deterministic and
rule-based, with the rules written out in each tool's spec, and they agree to the
cent on a worked example. There is no framework, no build step, and no server.

## The tools
1. **inventory-costing-engine** - command-line Python that maintains perpetual
   weighted-average cost per SKU, folds freight and import duty into landed cost,
   converts cases and kegs to hectolitres, and applies the CRA reduced-rate excise
   brackets to the beer packaged in the period.
2. **month-end-reconciliation** - a SQLite schema and query set with a standard-library
   Python runner that reconciles the perpetual valuation to the physical count,
   flags variances over a set tolerance, and totals closing inventory value and
   excise duty by category.

The excise rates are the CRA rates per hectolitre effective April 1, 2026, written
out in the costing engine and updated each April when CRA publishes the annual
adjustment.

## License
MIT, copyright Kevin Yu (github.com/exekyute).
