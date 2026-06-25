# Loan Servicing Toolkit

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a loan servicing analyst does, while
strengthening my foundational software development skills.

The repository holds two small tools that share one job: build an accurate
amortization schedule for a loan and present it as a clear, borrower-ready balance
summary. The first is a Python command-line utility and the second is a browser tool
written in plain HTML, CSS, and vanilla JavaScript, so the repository shows two
languages while staying entirely no-backend. Both are self-contained and rule-based,
built around clean business logic, careful input validation, and data integrity. All
sample data is synthetic.

## The tools

1. **[Amortization Schedule Generator](amortization-schedule-generator/)** is a
   Python utility that takes a loan principal, an annual interest rate, and a term in
   months, computes the level monthly payment, splits each payment into interest and
   principal with a running balance, reconciles the final period so the balance closes
   at exactly zero, and writes the schedule to a CSV. Money is handled with
   `decimal.Decimal` in whole cents using `ROUND_HALF_UP`, so no penny is ever lost
   or gained.
2. **[Loan Balance Dashboard](loan-balance-dashboard/)** is a single-page browser
   tool that loads that schedule CSV with the `FileReader` API and shows each
   period's payment, interest, principal, and remaining balance, with a summary line
   for total interest paid and total of payments over the life of the loan. Amounts
   are handled in whole cents and formatted with `Intl.NumberFormat`, so totals stay
   exact and free of floating-point artifacts.

## How they connect

The generator produces the file the dashboard reads. Run the generator on the sample
loan and it writes `schedule.csv`; the dashboard ships that same file in its
`sample_data/` and renders it. The shared worked example is a `1000.00` loan at `12%`
annual over `6` months. The level payment is `172.55`, and the final period
reconciles to `172.53` so the balance lands on exactly `0.00`. Loaded into the
dashboard, the figures match the generator: total interest paid `35.28`, total of
payments `1035.28`, final balance `0.00`. That example is documented in both tools'
`spec.md`.

## Running the tools

The Amortization Schedule Generator runs from a terminal in its own folder. It needs
Python 3.8 or newer and nothing else:

```
python amortize.py --principal 1000.00 --annual-rate 12 --term-months 6 --output sample_data/schedule.csv
python -m unittest discover -s tests -t . -v
```

The Loan Balance Dashboard opens by double-clicking its `index.html`. Pick
`sample_data/schedule.csv` to see the table and summary. Its `tests.html` opens the
same way and prints PASS or FAIL on the page.

Each tool folder has its own README with worked examples and screenshots, and a
`spec.md` describing purpose, inputs, validation, logic, outputs, and edge cases.

## Repository layout

```
loan-servicing-toolkit/
  LICENSE
  README.md
  amortization-schedule-generator/
  loan-balance-dashboard/
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
