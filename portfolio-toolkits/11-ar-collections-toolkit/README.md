# AR Collections Toolkit

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work an accounts receivable and collections analyst
does, while strengthening my foundational software development skills.

The repository holds two small tools that share one job: age open invoices and apply
late fees, then present the overdue accounts by bucket. The first is a Python
command-line engine and the second is a browser dashboard written in plain HTML,
CSS, and vanilla JavaScript, so the repository shows two languages while staying
entirely no-backend. Both are self-contained and rule-based, built around clean
separation of logic, careful input validation, and exact money handling. All sample
data is synthetic.

## The tools

1. **[AR Aging Engine](ar-aging-engine/)** is a Python tool (standard library) that
   reads a CSV of open invoices, computes days past due against a reference date,
   buckets each invoice, applies a late fee to overdue ones, and writes a per-invoice
   aging report.
2. **[Collections Dashboard](collections-dashboard/)** loads the aging report in the
   browser with the FileReader API and renders a color-coded table with the total
   outstanding per bucket.

## How they connect

The Python engine writes an aging report CSV. The browser dashboard reads that same
CSV and presents it. The two share one set of aging buckets (Current, 1-30, 31-60,
61-90, 90-plus) and agree on the numbers to the cent. For example, invoice
`INV-1004` at 90 days past due lands in the `61-90` bucket with a `$15.00` late fee
in both tools. Each tool's `spec.md` documents this hand-checked example. The Python
tool uses `decimal.Decimal` with `ROUND_HALF_UP`; the browser tool uses integer
cents and `Intl.NumberFormat`, so amounts never show floating-point artifacts.

## Running the tools

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

Each tool has its own README with the full walkthrough, and a `spec.md` covering its
purpose, inputs, validation rules, logic, outputs, and edge cases.

## Repository layout

```
ar-collections-toolkit/
  LICENSE
  README.md
  ar-aging-engine/          Python
  collections-dashboard/    browser
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
