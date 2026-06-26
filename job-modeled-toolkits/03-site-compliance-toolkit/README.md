# Site Compliance Toolkit

A personal project, one of several I build to model real-world job descriptions
and turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work an environmental project coordinator does,
while strengthening my foundational software development skills.

The repository holds three independent command-line tools written in plain
Python, each mapped to a core responsibility of the role. Each one is
self-contained, rule-based, and built around clean business logic, careful input
validation, and data integrity. Everything runs on your machine using only the
standard library. All sample data is synthetic.

## The tools

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

## How they connect

The deadline monitor reads the unified ledger that the aggregator builds. On the
sample data both tools agree that the ledger holds 3 distinct sites (Harbor Site,
North Site, Ridge Site), and the monitor then flags Ridge Site as a compliance gap
because it has operational activity but no tracked deadline. That shared count of 3
is hand-checked and noted in both tools' specs.

## Running the tools

Python 3.8 or newer, no third-party packages. Each tool ships a `unittest` suite.
From the repository root:

```
python -m unittest discover -s waste-fuel-aggregator/tests -v
python -m unittest discover -s deadline-monitor/tests -v
python -m unittest discover -s field-audit-validator/tests -v
```

Each tool folder has its own README with screenshots of the tool running, and a
`spec.md` with its design blueprint.

## Repository layout

```
site-compliance-toolkit/
├── waste-fuel-aggregator/    Tool 1
├── deadline-monitor/         Tool 2
└── field-audit-validator/    Tool 3
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
