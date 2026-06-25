# Budget and Forecast Toolkit

A personal project, one of several I build to model real-world job descriptions
and turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a financial analyst focused on corporate
budgeting and forecasting does, while strengthening my foundational software
development skills.

The repository holds three independent command-line tools written in plain
Python, each mapped to a core responsibility of the role. Each one is
self-contained, rule-based, and built around clean business logic, careful input
validation, and exact money math, using only the standard library. All sample
data is synthetic.

## The tools

1. **[Multi-Departmental Budget Consolidation Tool](budget-consolidation/)** reads
   a directory of individual departmental budget sheets, standardizes their
   formatting, merges duplicate line items, and writes one master corporate budget
   template.
2. **[Variance Analysis Report Writer](variance-analysis/)** compares the master
   budget against actual expenses, computes the variance for every department, and
   writes a summary of the departments that exceed budget parameters.
3. **[Cash Flow Moving-Average Forecaster](cashflow-forecaster/)** reads a history
   of monthly net cash flows and applies arithmetic moving averages to project the
   upcoming quarter and the cash runway.

## How they connect

The first two tools connect: the Variance Analysis tool reads the master budget
that the Consolidation tool produces, so a figure standardized and merged by the
first tool is the same figure the second tool reports against.

Every budget and variance figure is handled with `decimal.Decimal`, rounded half
up to cents, and printed in plain fixed-point notation, which keeps the numbers
exact and avoids the rounding drift of floating-point arithmetic.

## Running the tools

Python 3.10 or newer, no third-party packages. Each tool ships a `unittest`
suite. From the repository root:

```
python -m unittest discover -s budget-consolidation/tests -v
python -m unittest discover -s variance-analysis/tests -v
python -m unittest discover -s cashflow-forecaster/tests -v
```

Each tool folder has its own README with worked examples and screenshots, and a
`spec.md` describing its inputs, validation, logic, outputs, and edge cases.

## Repository layout

```
budget-forecast-toolkit/
├── budget-consolidation/    Tool 1
├── variance-analysis/       Tool 2
└── cashflow-forecaster/     Tool 3
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
