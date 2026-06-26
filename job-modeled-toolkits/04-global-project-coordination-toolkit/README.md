# Global Project Coordination Toolkit

A personal project, one of several I build to model real-world job descriptions
and turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a project coordinator supporting
international social-impact projects does, while strengthening my foundational
software development skills.

The repository holds three independent command-line tools written in plain
Python, each mapped to a core responsibility of the role: tracking budgets across
project phases, processing consultant invoices in different currencies, and
onboarding contractors with the right regional compliance documents. Each one is
self-contained, rule-based, and built around clean business logic, careful input
validation, and data integrity, using only the standard library. All sample data,
templates, and names are synthetic.

## The tools

1. **[Multi-Currency Consultant Ledger](multi-currency-ledger/)** parses consultant
   invoices submitted in different currencies, converts each to a USD base using an
   editable rate dictionary, and reconciles the total against an approved grant. It
   writes a central budget file.
2. **[Milestone-Driven Burn Rate Tracker](burn-rate-tracker/)** reads that central
   budget file, applies project phase costs on top, and reports the running burn
   rate against the grant fund after each phase.
3. **[Contractor Onboarding Package Builder](onboarding-package-builder/)** takes a
   contractor's region and role, resolves the required compliance documents from
   editable rule tables, and copies those templates into a personalized vendor
   folder.

## How they connect

The first two tools run as a pipeline. The ledger writes a `central_budget.json`
holding the grant total and the consultant spend in the base currency. The burn
rate tracker reads that same file as its starting figure instead of recomputing
it, so the two tools always agree. For the seeded sample data the ledger reports a
consultant spend of 248,600.00 against a 250,000.00 grant, and the burn rate
tracker opens from exactly that figure, a 99.44 percent starting burn rate. That
hand-checked value is documented in the burn rate tracker's `spec.md`.

## Running the tools

Python 3.10 or newer, no third-party packages. All money math uses
`decimal.Decimal` with half-up rounding and prints as fixed-point values. Each
tool ships a `unittest` suite. From the repository root:

```
python -m unittest discover -s multi-currency-ledger/tests -v
python -m unittest discover -s burn-rate-tracker/tests -v
python -m unittest discover -s onboarding-package-builder/tests -v
```

Each tool folder has its own README with screenshots of the tool running, and a
`spec.md` with its design blueprint.

## Repository layout

```
global-project-coordination-toolkit/
├── multi-currency-ledger/        Tool 1, produces central_budget.json
├── burn-rate-tracker/            Tool 2, consumes central_budget.json
└── onboarding-package-builder/   Tool 3, independent
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
