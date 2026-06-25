# Fund Administration Toolkit

A personal project, one of several I build to model real-world job descriptions
and turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a fund administration analyst does, while
strengthening my foundational software development skills.

The repository holds two small tools that share one job: allocate a fund's capital
call across its investors, keep the records accurate to the penny, and present a
clear investor-facing summary. The first is a Python command-line utility and the
second is a browser tool written in plain HTML, CSS, and vanilla JavaScript, so the
repository shows two languages while staying entirely no-backend. Both are
self-contained and rule-based, built around clean business logic, careful input
validation, and data integrity. All sample data is synthetic.

## The tools

1. **[Capital Call Allocator](capital-call-allocator/)** is a Python utility that
   takes a fund's total capital call and a CSV of investor commitments, splits the
   call pro-rata by commitment, reconciles the rounding so the per-investor amounts
   sum to the call total exactly, and writes a per-investor allocation CSV. Money
   is handled with `decimal.Decimal` in whole cents using the largest-remainder
   method, so no penny is ever lost or gained.
2. **[Investor Allocation Dashboard](investor-allocation-dashboard/)** is a
   single-page browser tool that loads that allocation CSV with the `FileReader`
   API and shows each investor's commitment, ownership percentage, called amount,
   and remaining unfunded commitment, with a fund-level summary line. Amounts are
   handled in whole cents and formatted with `Intl.NumberFormat`, so totals stay
   exact and free of floating-point artifacts.

## How they connect

The allocator produces the file the dashboard reads. Run the allocator on the
sample commitments and it writes `allocation.csv`; the dashboard ships that same
file in its `sample_data/` and renders it. The shared worked example is a
250,000.00 call across five investors. The per-investor amounts first round to
249,999.99, one cent short, so the largest dropped fraction (Brightwater LP)
receives the reconciling cent. Loaded into the dashboard, the figures match the
allocator and the total called reads 250,000.00 exactly. That example is documented
in both tools' `spec.md`.

## Running the tools

The Capital Call Allocator runs from a terminal in its own folder. It needs Python
3.8 or newer and nothing else:

```
python allocate.py --call-total 250000.00 --commitments sample_data/commitments.csv --output sample_data/allocation.csv
python -m unittest discover -s tests -t . -v
```

The Investor Allocation Dashboard opens by double-clicking its `index.html`. Pick
`sample_data/allocation.csv` to see the table and summary. Its `tests.html` opens
the same way and prints PASS or FAIL on the page.

Each tool folder has its own README with worked examples and screenshots, and a
`spec.md` describing purpose, inputs, validation, logic, outputs, and edge cases.

## Repository layout

```
fund-administration-toolkit/
  LICENSE
  README.md
  capital-call-allocator/
  investor-allocation-dashboard/
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
