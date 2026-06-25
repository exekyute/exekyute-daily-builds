# Site Compliance Toolkit

This is a personal project, one of several where I turn a real job description into
working software. I take the responsibilities listed for a role, then build small
focused tools that practice the same skills the job asks for. The aim is to
strengthen my foundational Python while producing something concrete that I can
run, test, and explain.

This repository models the work of an Environmental Project Coordinator. It
contains three independent command-line tools, each mapped to a core
responsibility from that role. Each one focuses on clear business logic, careful
input validation, and data integrity. None of them use any external services.

## The three tools

1. **[Regional Waste and Fuel Log Aggregator](waste-fuel-aggregator/)** reads a
   folder of monthly site spreadsheets that each name their columns differently,
   normalizes them to one schema, validates every row, and combines them into a
   single unified ledger.
2. **[Regulatory Deadline Monitor](deadline-monitor/)** reads a log of compliance
   requirements, compares each due date to today, and prints a dashboard sorted by
   urgency, from overdue through upcoming.
3. **[Operational Field Audit Validator](field-audit-validator/)** is an
   interactive questionnaire for site inspectors that forces valid answers and
   records each finished audit as one timestamped line.

Each tool folder has its own README with screenshots of the tool running, and a
`spec.md` with its design blueprint.

## How the tools connect

The deadline monitor reads the unified ledger that the aggregator builds. On the
sample data both tools agree that the ledger holds 3 distinct sites (Harbor Site,
North Site, Ridge Site), and the monitor then flags Ridge Site as a compliance gap
because it has operational activity but no tracked deadline. That shared count of 3
is hand-checked and noted in both tools' specs.

All sample data in this repository is synthetic. No real site or operational
information is included.

## Repository layout

```
site-compliance-toolkit/
├── waste-fuel-aggregator/    Tool 1
├── deadline-monitor/         Tool 2
└── field-audit-validator/    Tool 3
```

## Requirements

Python 3.8 or newer. No third-party packages.

## Running the tests

Each tool ships a `unittest` suite. From the repository root:

```
python -m unittest discover -s waste-fuel-aggregator/tests -v
python -m unittest discover -s deadline-monitor/tests -v
python -m unittest discover -s field-audit-validator/tests -v
```
