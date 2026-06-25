# Budget and Forecast Toolkit

This is a personal project, one of several where I turn a real job description into working software.
I take the responsibilities listed for a role, then build small focused tools that practice the same
skills the job asks for. The aim is to strengthen my foundational Python while producing something
concrete that I can run, test, and explain.

This repository models the work of a Financial Analyst focused on corporate budgeting and
forecasting. It contains three independent command-line tools, each mapped to a core responsibility
from that role. Each one focuses on clear business logic, careful input validation, and data
integrity, written as plain, rule-based Python using only the standard library.

## The three tools

1. **[Multi-Departmental Budget Consolidation Tool](budget-consolidation/)** reads a directory of
   individual departmental budget sheets, standardizes their formatting, merges duplicate line items,
   and writes one master corporate budget template.
2. **[Variance Analysis Report Writer](variance-analysis/)** compares the master budget against actual
   expenses, computes the variance for every department, and writes a summary of the departments that
   exceed budget parameters.
3. **[Cash Flow Moving-Average Forecaster](cashflow-forecaster/)** reads a history of monthly net cash
   flows and applies arithmetic moving averages to project the upcoming quarter and the cash runway.

The first two tools connect: the Variance Analysis tool reads the master budget that the Consolidation
tool produces, so a figure standardized and merged by the first tool is the same figure the second
tool reports against.

Each tool folder has its own README with screenshots of the tool running, and a `spec.md` with its
design blueprint.

All sample data in this repository is synthetic.

## Repository layout

```
budget-forecast-toolkit/
├── budget-consolidation/    Tool 1
├── variance-analysis/       Tool 2
└── cashflow-forecaster/     Tool 3
```

## Requirements

Python 3.10 or newer. No third-party packages.

## Money math

Every budget and variance figure is handled with `decimal.Decimal`, rounded half up to cents, and
printed in plain fixed-point notation. This keeps the numbers exact and avoids the rounding drift of
floating-point arithmetic.

## Running the tests

Each tool ships a `unittest` suite. From the repository root:

```
python -m unittest discover -s budget-consolidation/tests -v
python -m unittest discover -s variance-analysis/tests -v
python -m unittest discover -s cashflow-forecaster/tests -v
```
