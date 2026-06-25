# Rent Roll Toolkit

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a property management and leasing analyst does,
while strengthening my foundational software development skills.

The repository holds seven small tools that follow the leasing cycle end to end:
bill the rent, plan the renewals, chase the delinquencies, and settle the deposits
at move-out. The first three jobs are matched pairs, one Python command-line tool
that writes a CSV and one browser tool that loads it; the deposit job is a Python
reconciliation tool. Every tool is self-contained, rule-based, and built around
clean business logic, careful input validation, and exact money math. There is no
framework, no build step, and no server: the Python tools use the standard library
only, and the browser tools open by double-clicking their HTML file with any loaded
file read on your machine. All sample data is synthetic.

## The tools

1. **Rent billing**
   - [Rent Roll and Proration Calculator](01-rent-roll-proration-calculator/)
     prorates partial-month rent by actual occupied days, applies late fees to
     overdue balances, and writes a per-unit rent roll.
   - [Lease and Rent Roll Dashboard](02-lease-rent-roll-dashboard/) loads that rent
     roll and renders the per-unit table with a billed total and a flag for leases
     expiring within a window.
2. **Renewals**
   - [Lease Renewal and Escalation Scheduler](03-lease-renewal-escalation-scheduler/)
     computes each lease's next term and escalated rent and flags which need a
     renewal notice now.
   - [Renewal Pipeline Tracker](04-renewal-pipeline-tracker/) loads the renewals and
     shows the pipeline grouped by status, sortable so the most urgent come first.
3. **Delinquency**
   - [Delinquency and Aging Ledger](05-delinquency-aging-ledger/) ages overdue
     balances into buckets, applies a late fee past a grace period, and totals what
     is owed.
   - [Delinquency Dashboard](06-delinquency-dashboard/) loads the aging report and
     shows delinquency by bucket with totals, most overdue first.
4. **Deposits**
   - [Security Deposit Reconciliation](07-security-deposit-reconciliation/)
     reconciles each deposit against itemized move-out deductions into a refund owed
     or a balance owed.

## How they connect

Each Python tool writes the exact CSV its browser partner reads, and the numbers
agree to the cent. A few worked examples carried across a pair:

- Unit 101 prorates to `$750.00` for a mid-month move-in in the calculator, and the
  dashboard reads the same `$750.00`.
- Unit 101 escalates to `$1,560.00` at 4 percent in the scheduler, and the tracker
  reads the same `$1,560.00`.
- The ledger totals `$10,807.50` owed across the aging buckets, and the dashboard
  totals the same figure.

The tools share one synthetic property, so the same units and tenants run through
every file and tell one connected story. Python tools use `decimal.Decimal` with
half-up rounding, printed fixed-point, and browser tools work in integer cents
formatted with `Intl.NumberFormat`, so the numbers stay exact across the handoff.

## Running the tools

Python tools, from inside the tool's folder:

```
python cli.py
python -m unittest -v
```

Browser tools: double-click `index.html` to use the tool, or `tests.html` to run
its checks. Nothing to install.

Each tool folder has its own README with worked examples and screenshots, and a
`spec.md` describing purpose, inputs, validation, logic, outputs, and edge cases.

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
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
