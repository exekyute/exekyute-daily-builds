# Pension Administration Toolkit

A personal project, one of several I build to model real-world job descriptions
and turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a business analyst in pension administration
does, while strengthening my foundational software development skills.

The repository holds three independent command-line tools written in plain
Python, each mapped to a core responsibility of the role. Each one is
self-contained, rule-based, and built around clean business logic, careful input
validation, and data integrity, using only the standard library. All sample data
is synthetic.

## The tools

1. **[Benefit Formula Engine](benefit-formula-engine/)** calculates a monthly
   retirement payout from salary history, credited service, and retirement age,
   using configurable plan rules.
2. **[Ledger Reconciliation Tool](ledger-reconciliation/)** compares an internal
   payroll file against a trustee file by Employee ID and reports every variance.
3. **[QA Test-Case Generator](qa-test-generator/)** builds edge-case scenarios,
   runs them through the Benefit Engine, and writes a test-case table used to
   validate calculation output.

## How they connect

The QA Test-Case Generator drives the Benefit Formula Engine, feeding it built
edge-case scenarios and recording the results into a test-case table, so the
generator and the engine stay in agreement on every documented case.

## Running the tools

Python 3.10 or newer, no third-party packages. Each tool ships a `unittest`
suite. From the repository root:

```
python -m unittest discover -s benefit-formula-engine/tests -v
python -m unittest discover -s ledger-reconciliation/tests -v
python -m unittest discover -s qa-test-generator/tests -v
```

Each tool folder has its own README with screenshots of the tool running, and a
`spec.md` with its design blueprint.

## Repository layout

```
pension-admin-toolkit/
├── benefit-formula-engine/    Tool 1
├── ledger-reconciliation/     Tool 2
└── qa-test-generator/         Tool 3
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
