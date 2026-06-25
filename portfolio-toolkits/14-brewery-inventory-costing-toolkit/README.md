# Brewery Inventory Costing Toolkit

A personal project, one of several I build to model real-world job descriptions
and turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a junior inventory accountant at a craft
brewery does, while strengthening my foundational software development skills.

The repository holds two tools that run in sequence. The costing engine keeps
perpetual weighted-average inventory and computes federal excise duty, writing a
valuation CSV and an excise summary CSV. The reconciliation tool reads those two
files plus a physical count sheet, reconciles book to count, flags variances over
tolerance, and rolls up closing value and duty for month-end. Both are
self-contained and rule-based, with the rules written out in each tool's spec, and
they agree to the cent on a worked example. There is no framework, no build step,
and no server. All sample data is synthetic.

## The tools

1. **[Inventory Costing Engine](inventory-costing-engine/)** is command-line Python
   (standard library) that maintains perpetual weighted-average cost per SKU, folds
   freight and import duty into landed cost, converts cases and kegs to hectolitres,
   and applies the CRA reduced-rate excise brackets to the beer packaged in the
   period.
2. **[Month-End Reconciliation](month-end-reconciliation/)** is a SQLite schema and
   query set with a standard-library Python runner that reconciles the perpetual
   valuation to the physical count, flags variances over a set tolerance, and totals
   closing inventory value and excise duty by category.

## How they connect

The costing engine writes the valuation and excise CSVs that the reconciliation
tool reads alongside the physical count sheet, so book and count are compared on the
same figures and the two tools agree to the cent. The excise rates are the CRA rates
per hectolitre effective April 1, 2026, written out in the costing engine and
updated each April when CRA publishes the annual adjustment.

## Running the tools

The Inventory Costing Engine runs with Python 3 (standard library only) from its
folder. The Month-End Reconciliation runs through its standard-library Python runner,
which loads the SQLite schema and prints the query results. Each tool folder has its
own README with the exact commands, a passing test run, and a `spec.md` covering
purpose, inputs, validation, logic, outputs, and edge cases.

## Repository layout

```
brewery-inventory-costing-toolkit/
  LICENSE
  README.md
  inventory-costing-engine/    Python
  month-end-reconciliation/    SQL (SQLite) + Python runner
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
