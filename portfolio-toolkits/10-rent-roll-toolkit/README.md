# Rent Roll Toolkit

A personal project, one of several I build to model real world job descriptions and
turn them into functional business utilities. The goal is to practice applied problem
solving on the kind of work a property management and leasing analyst does, while
strengthening my foundational software development skills.

The repository holds eight small tools in four matched pairs. Each pair is one Python
command-line tool that writes a CSV and one browser tool, written in plain HTML, CSS,
and vanilla JavaScript, that loads that CSV. Every tool is self contained, rule based,
and built around clean business logic, careful input validation, and exact money math.
There is no AI, no machine learning, no framework, no build step, and no server. The
Python tools use the standard library only. The browser tools open by double-clicking
their HTML file, and any file you load is read in your browser and never sent anywhere.

## The four pairs

The tools follow the work end to end: bill the rent, plan the renewals, chase the
delinquencies, and settle the deposits at move-out. In each pair the Python tool
produces a CSV and the browser tool reads it.

1. **Rent billing**
   - [Rent Roll and Proration Calculator](01-rent-roll-proration-calculator/) prorates
     partial-month rent by actual occupied days, applies late fees to overdue balances,
     and writes a per-unit rent roll.
   - [Lease and Rent Roll Dashboard](02-lease-rent-roll-dashboard/) loads that rent roll
     and renders the per-unit table with a billed total and a flag for leases expiring
     within a window.
2. **Renewals**
   - [Lease Renewal and Escalation Scheduler](03-lease-renewal-escalation-scheduler/)
     computes each lease's next term and escalated rent and flags which need a renewal
     notice now.
   - [Renewal Pipeline Tracker](04-renewal-pipeline-tracker/) loads the renewals and
     shows the pipeline grouped by status, sortable so the most urgent come first.
3. **Delinquency**
   - [Delinquency and Aging Ledger](05-delinquency-aging-ledger/) ages overdue balances
     into buckets, applies a late fee past a grace period, and totals what is owed.
   - [Delinquency Dashboard](06-delinquency-dashboard/) loads the aging report and shows
     delinquency by bucket with totals, most overdue first.
4. **Deposits**
   - [Security Deposit Reconciliation](07-security-deposit-reconciliation/) reconciles
     each deposit against itemized move-out deductions into a refund owed or a balance
     owed.
   - [Deposit Settlement Dashboard](08-deposit-settlement-dashboard/) loads the
     reconciliation and splits refunds owed from balances owed, with totals.

## How they connect

Each Python tool writes the exact CSV its browser partner reads, and the numbers agree
to the cent. A few worked examples carried across both tools in a pair:

- Unit 101 prorates to `$750.00` for a mid-month move-in in the calculator, and the
  dashboard reads the same `$750.00`.
- Unit 101 escalates to `$1,560.00` at 4 percent in the scheduler, and the tracker reads
  the same `$1,560.00`.
- The ledger totals `$10,807.50` owed across the aging buckets, and the dashboard totals
  the same figure.
- The reconciliation owes `$4,300.00` in refunds and `$300.00` in balances, and the
  settlement dashboard totals the same.

The tools share one synthetic property, so the same units and tenants run through every
file and tell one connected story.

## How each tool is built

- Python tools split the work into three files: pure logic, validation, and a thin CLI
  wrapper. Money uses `decimal.Decimal` with half-up rounding, printed fixed-point, and
  dates are explicit `YYYY-MM-DD`. Each ships a `unittest` suite.
- Browser tools split pure logic into its own `.js` file, written as functions that take
  input and return values with no DOM access, with a thin page script for wiring. Money
  is handled in integer cents and formatted with `Intl.NumberFormat`. Each ships a
  `tests.html` that runs its logic and prints PASS or FAIL on the page.
- Every tool validates its input the same way: a whole-file problem like a missing
  column stops the run with one message, while a single bad row is skipped and reported
  by line number so one bad row never hides the rest.

## Running the tools

Python tools, from inside the tool's folder:

```
python cli.py
python -m unittest -v
```

Browser tools: double-click `index.html` to use the tool, or `tests.html` to run its
checks. Nothing to install.

Each tool folder has its own README with worked examples and screenshots, a `spec.md`
describing purpose, inputs, validation, logic, outputs, and edge cases, sample data, and
a test suite.

## Repository layout

```
rent-roll-toolkit/
  LICENSE
  README.md
  01-rent-roll-proration-calculator/      Python
  02-lease-rent-roll-dashboard/           browser
  03-lease-renewal-escalation-scheduler/  Python
  04-renewal-pipeline-tracker/            browser
  05-delinquency-aging-ledger/            Python
  06-delinquency-dashboard/               browser
  07-security-deposit-reconciliation/     Python
  08-deposit-settlement-dashboard/        browser
```

## Privacy

The browser tools run entirely in your browser. Files you load are read with the
`FileReader` API and stay on your machine.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
