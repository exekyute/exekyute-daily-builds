# AR Collections Toolkit

Two small, no-backend tools for accounts receivable and collections work: a Python command-line
engine that ages open invoices and applies late fees, and a browser dashboard that reads the
engine's report and shows overdue accounts by bucket. Both are deterministic and rule-based,
with the rules written out in each tool's spec.

This is one of several personal projects I build to model real job descriptions and turn them into
working business utilities. The goal is to practice applied problem-solving and strengthen my
foundational software development skills: clean separation of logic, careful input validation, and
exact money handling.

## The two tools

| Tool | Language | What it does |
|------|----------|--------------|
| [ar-aging-engine](ar-aging-engine/) | Python (standard library) | Reads a CSV of open invoices, computes days past due against a reference date, buckets each invoice, applies a late fee to overdue ones, and writes a per-invoice aging report. |
| [collections-dashboard](collections-dashboard/) | HTML, CSS, vanilla JavaScript | Loads the aging report in the browser with the FileReader API and renders a color-coded table with the total outstanding per bucket. |

## How they connect

The Python engine writes an aging report CSV. The browser dashboard reads that same CSV and presents
it. The two share one set of aging buckets (Current, 1-30, 31-60, 61-90, 90-plus) and agree on the
numbers to the cent. For example, invoice `INV-1004` at 90 days past due lands in the `61-90` bucket
with a `$15.00` late fee in both tools. Each tool's `spec.md` documents this hand-checked example.

## Quick start

Age the sample invoices and write the report:

```
cd ar-aging-engine
python -m unittest -v
python cli.py --reference-date 2026-06-12
```

Then open the dashboard and load the report:

1. Double-click `collections-dashboard/index.html`.
2. Choose `collections-dashboard/sample-data/aging-report.csv`.
3. Review the per-bucket summary and the color-coded invoice table.

Each tool has its own README with the full walkthrough, and a `spec.md` covering its purpose,
inputs, validation rules, logic, outputs, and edge cases.

## Design notes

- Money is exact. The Python tool uses `decimal.Decimal` with `ROUND_HALF_UP`; the browser tool uses
  integer cents and `Intl.NumberFormat`, so amounts never show floating-point artifacts.
- Logic is separated from input handling and presentation in both tools, and each ships a test run
  you can see pass (a `unittest` suite for the engine, a `tests.html` page for the dashboard).
- Nothing leaves your machine. The engine reads and writes local files; the dashboard reads the CSV
  in the browser and sends it nowhere.

## License

MIT. See [LICENSE](LICENSE). Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
