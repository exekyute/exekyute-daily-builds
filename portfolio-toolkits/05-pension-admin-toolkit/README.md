# Pension Administration Toolkit

This is a personal project, one of several where I turn a real job description into working
software. I take the responsibilities listed for a role, then build small focused tools that
practice the same skills the job asks for. The aim is to strengthen my foundational Python
while producing something concrete that I can run, test, and explain.

This repository models the work of a Business Analyst in Pension Administration. It contains
three independent command-line tools, each mapped to a core responsibility from that role.
Each one focuses on clear business logic, careful input validation, and data integrity.

## The three tools

1. **[Benefit Formula Engine](benefit-formula-engine/)** calculates a monthly retirement payout
   from salary history, credited service, and retirement age, using configurable plan rules.
2. **[Ledger Reconciliation Tool](ledger-reconciliation/)** compares an internal payroll file
   against a trustee file by Employee ID and reports every variance.
3. **[QA Test-Case Generator](qa-test-generator/)** builds edge-case scenarios, runs them through
   the Benefit Engine, and writes a test-case table used to validate calculation output.

Each tool folder has its own README with screenshots of the tool running.

All sample data in this repository is synthetic. No real member information is included.

## Repository layout

```
pension-admin-toolkit/
├── benefit-formula-engine/    Tool 1
├── ledger-reconciliation/     Tool 2
└── qa-test-generator/         Tool 3
```

Each tool folder also includes a `spec.md` with its design blueprint.

## Requirements

Python 3.10 or newer. No third-party packages.

## Running the tests

Each tool ships a `unittest` suite. From the repository root:

```
python -m unittest discover -s benefit-formula-engine/tests -v
python -m unittest discover -s ledger-reconciliation/tests -v
python -m unittest discover -s qa-test-generator/tests -v
```
