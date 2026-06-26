# Membership Services Toolkit

A personal project, one of several I build to model real-world job descriptions
and turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a membership services coordinator does,
processing renewals and keeping the member database and the Excel worklist in
agreement, while strengthening my foundational software development skills.

The repository holds three small tools that share one data story. A SQL tool runs
the saved membership reports and writes a renewal worklist CSV. An Excel VBA tool
imports that CSV and builds the formatted, color-flagged worklist with the totals
the manager reviews. A browser dashboard reads the same CSV and shows the week at a
glance. All three are self-contained and rule-based, with the rules written out in
each tool's spec, and they agree to the cent: total dues 1,733.75, HST 225.39, late
fees 25.00, grand total billed 1,984.14. There is no framework, no build step, and
no server, and nothing is uploaded. All sample data is synthetic.

## The tools

1. **[Membership Reporting (SQL)](01-membership-reporting-sql/)** runs SQLite
   reports for the weekly expiring and lapsed worklists, the monthly dues summary
   with HST, and the reconciliation counts. It writes the renewal worklist CSV the
   other two tools read.
2. **[Renewal Worklist (Excel VBA)](02-renewal-worklist-vba/)** is a macro that
   imports the CSV and builds the formatted, flagged worklist with dues, HST,
   late-fee, and grand totals.
3. **[Renewal Dashboard (browser)](03-renewal-dashboard-browser/)** reads the CSV
   and shows counts, dues by tier, and the totals at a glance.

## How they connect

The SQL tool is the anchor: it runs here, applies HST with `Decimal` rounding, and
checks every total against the hand-checked figures in its spec. The Excel and
browser tools reproduce those same figures, so the three agree to the cent.

## Running the tools

The SQL tool runs through its standard-library Python runner against the SQLite
sample data. The browser dashboard opens by double-clicking its HTML file. The
Excel VBA macro is imported as a `.bas` module into a workbook and run from there.
Each tool folder has its own README with the exact steps and a `spec.md` covering
purpose, inputs, validation, logic, outputs, and edge cases.

## Repository layout

```
membership-services-toolkit/
  LICENSE
  README.md
  01-membership-reporting-sql/      SQL (SQLite) + Python runner
  02-renewal-worklist-vba/          Excel VBA
  03-renewal-dashboard-browser/     browser
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
