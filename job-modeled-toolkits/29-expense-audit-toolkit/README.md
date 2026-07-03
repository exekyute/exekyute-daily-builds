# Expense and T&E Audit Toolkit

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a travel and expense analyst does, checking a batch
of expenses against policy and working the exceptions, while strengthening my
foundational software development skills.

This toolkit has two tools. A command-line Python engine checks every expense against a
policy and flags the mileage mismatches, over-cap amounts, missing receipts, and
duplicates. A browser app shows the same batch as a review queue, where clean lines
approve on their own and flagged lines get an approve or reject with a reason, saved in
the browser. Each tool is self-contained and rule-based, with the rules written out in
its own `spec.md`, and there is no framework, no build step, and no server. The sample
data is synthetic, and the policy uses Canadian conventions such as a per-kilometre
mileage rate that is meant to be set to the current prescribed allowance.

## The tools
1. **[Expense auditor](01-expense-auditor/)** command-line Python that checks expenses
   against the policy and writes the flagged batch.
2. **[Expense review app](02-expense-review/)** a browser review queue that shows the
   flags, takes approve and reject decisions, persists them, and prints a report.

## How they connect

The auditor writes `audited.csv` from `expenses.csv` and `policy.csv`. The app reads the
same input format and reproduces every flag in JavaScript, so the two agree to the cent.
The shared hand-check is a 250 km mileage claim at 0.70 per km, which both work out to
175.00, and a batch of seven expenses that claims 890.00 with 475.00 flagged for review.
The engine's `unittest` suite and the app's `tests.html` both confirm these numbers.

## Running the tools

Python 3 runs the engine. The app needs only a browser.

```
# 01 expense auditor
python -m unittest
python cli.py
```

Open `02-expense-review/index.html` in a browser for the app, and
`02-expense-review/tests.html` for its test page. Each tool folder has its own README and
`spec.md`.

## Repository layout
```
29-expense-audit-toolkit/
  LICENSE
  README.md
  01-expense-auditor/
  02-expense-review/
```

## License
Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
