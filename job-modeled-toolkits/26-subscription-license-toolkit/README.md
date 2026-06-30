# Subscription and License Manager Toolkit

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a software asset or subscription manager does,
keeping a company's SaaS plans costed, used, and renewed on time, while
strengthening my foundational software development skills.

This toolkit has two tools. A command-line Python engine costs a subscription
portfolio: the monthly and annual spend, the seats paid for against the seats in
use, the waste on unused seats, and the renewals coming up. A browser app puts the
same portfolio in an editable table, recomputes as you change it, keeps the list in
your browser between visits, and prints a clean report. Each tool is self-contained
and rule-based, with the rules written out in its own `spec.md`, and there is no
framework, no build step, and no server. The sample data is synthetic, seeded so one
run touches a clean plan, an underused auto-renewing plan, a flat plan, a fully used
plan, an expired plan, and a renewal due within the month.

## The tools
1. **[Subscription ledger](01-subscription-ledger/)** command-line Python that costs
   the portfolio and writes a normalized CSV with each plan's spend, seat waste,
   renewal status, and suggested action.
2. **[License manager app](02-license-manager/)** a browser tool that shows the same
   portfolio in an editable table, recomputes live, persists in the browser, and
   prints a report.

## How they connect

The ledger writes `subscriptions_normalized.csv` from `subscriptions.csv`. The app
reads the same input format and recomputes every figure in JavaScript, so the two
agree to the cent. The shared hand-check is subscription S-01: 50 seats at 12.00,
38 used, costing 600.00 a month with 12 unused seats worth 1,728.00 a year. Across
the sample the portfolio is 3,675.00 a month and 11,808.00 of annual seat waste. The
engine's `unittest` suite and the app's `tests.html` both confirm these numbers.

## Running the tools

Python 3 runs the engine. The app needs only a browser.

```
# 01 subscription ledger
python -m unittest
python cli.py --asof 2026-06-30
```

Open `02-license-manager/index.html` in a browser for the app, and
`02-license-manager/tests.html` for its test page. Each tool folder has its own
README and `spec.md`.

## Repository layout
```
26-subscription-license-toolkit/
  LICENSE
  README.md
  01-subscription-ledger/
  02-license-manager/
```

## License
Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
