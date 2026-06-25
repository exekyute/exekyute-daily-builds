# Global Project Coordination Toolkit

This is a personal project, one of several where I turn a real job description into working software.
I take the responsibilities listed for a role, then build small focused tools that practice the same
skills the job asks for. The aim is to strengthen my foundational Python while producing something
concrete that I can run, test, and explain.

This repository models the work of a Project Coordinator supporting international social-impact
projects: tracking budgets across project phases, processing consultant invoices in different
currencies, and onboarding contractors with the right regional compliance documents. It contains
three independent command-line tools, each mapped to a core responsibility from that role. Each one
focuses on clear business logic, careful input validation, and data integrity. They are plain,
rule-based Python with no third-party dependencies.

## The three tools

1. **[Multi-Currency Consultant Ledger](multi-currency-ledger/)** parses consultant invoices submitted
   in different currencies, converts each to a USD base using an editable rate dictionary, and
   reconciles the total against an approved grant. It writes a central budget file.
2. **[Milestone-Driven Burn Rate Tracker](burn-rate-tracker/)** reads that central budget file, applies
   project phase costs on top, and reports the running burn rate against the grant fund after each
   phase.
3. **[Contractor Onboarding Package Builder](onboarding-package-builder/)** takes a contractor's region
   and role, resolves the required compliance documents from editable rule tables, and copies those
   templates into a personalized vendor folder.

Each tool folder has its own README with screenshots of the tool running, and a `spec.md` with its
design blueprint.

## How the tools connect

The first two tools run as a pipeline. The ledger writes a `central_budget.json` holding the grant
total and the consultant spend in the base currency. The burn rate tracker reads that same file as
its starting figure instead of recomputing it, so the two tools always agree on the same number. For
the seeded sample data the ledger reports a consultant spend of 248,600.00 against a 250,000.00 grant,
and the burn rate tracker opens from exactly that figure, a 99.44 percent starting burn rate. That
hand-checked value is documented in the burn rate tracker's `spec.md`.

## Repository layout

```
global-project-coordination-toolkit/
├── multi-currency-ledger/        Tool 1, produces central_budget.json
├── burn-rate-tracker/            Tool 2, consumes central_budget.json
└── onboarding-package-builder/   Tool 3, independent
```

## Requirements

Python 3.10 or newer. No third-party packages. All money math uses `decimal.Decimal` with half-up
rounding and prints as fixed-point values.

## Running the tests

Each tool ships a `unittest` suite. From the repository root:

```
python -m unittest discover -s multi-currency-ledger/tests -v
python -m unittest discover -s burn-rate-tracker/tests -v
python -m unittest discover -s onboarding-package-builder/tests -v
```

All sample data, templates, and names in this repository are synthetic. No real financial, consultant,
or contractor information is included.
