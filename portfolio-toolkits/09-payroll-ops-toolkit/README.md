# Payroll Operations Toolkit

A personal project, one of several I build to model real world job descriptions
and turn them into functional business utilities. The goal is to practice
applied problem solving on the kind of work a payroll operations analyst does,
while strengthening my foundational software development skills.

The repository holds two small tools that follow one pay run from raw timesheet
to reviewed pay register. They are written in two languages to show more than
one stack in a single repo while staying simple to run. Both are self contained,
rule based, and built around clean business logic, careful input validation, and
exact money math. There is no framework, no build step, and no server. Any file
you load in the browser tool is read on your
machine and never sent anywhere.

The tools target a Canadian payroll context. Gross to net covers overtime, CPP,
EI, flat combined federal and provincial income tax, and pre-tax and post-tax
deductions, with amounts in Canadian dollars.

## The two tools

1. **[Payroll Run Calculator](01-payroll-run-calculator/)** is a Python command
   line tool that reads a timesheet CSV of hourly and salaried employees and
   computes gross pay, overtime past the weekly threshold, CPP, EI, income tax,
   and pre-tax and post-tax deductions, then writes a per-employee payroll
   register CSV and prints a run summary.
2. **[Net Pay Dashboard](02-net-pay-dashboard/)** is a single-page browser tool
   that loads that register CSV with the FileReader API and renders a table of
   each employee's gross, overtime, total deductions, income tax, and net pay,
   with a run summary showing total gross and total net.

## How they connect

The Payroll Run Calculator produces the payroll register, and the Net Pay
Dashboard reads that same register. Both ship the register file,
`payroll_register.csv`, so a single run and a single load exercise the whole
flow. The worked example carried through both tools is employee E002, Bianca
Tran, an hourly worker with overtime: the calculator computes a gross of
`$1,590.00` and a net of `$1,094.01`, and the dashboard displays the same net of
`$1,094.01`, matching to the cent. The example is documented in both tools'
`spec.md`.

## Running the tools

The Payroll Run Calculator runs with Python from its folder:

```
python payroll_cli.py data/sample_timesheet.csv -o data/payroll_register.csv
```

It uses the Python standard library only, with nothing to install. Its tests run
with `python -m unittest discover -s tests`.

The Net Pay Dashboard opens by double-clicking its `index.html` in a web
browser, with nothing to install. It also has a `tests.html` that runs its logic
against hand-worked numbers and prints PASS or FAIL on the page, so the checks
run with no build tooling.

Each tool folder has its own README with worked examples and screenshots, a
`spec.md` describing purpose, inputs, validation, logic, outputs, and edge
cases, sample data, and a test suite.

## How each tool is built

- Pure calculation logic lives in its own file, written as functions that take
  input and return values, with no file, console, or DOM access.
- A thin wrapper handles reading input and presenting results.
- Input validation is separate and reports problems with clear messages rather
  than guessing, so bad rows are flagged instead of producing a wrong paycheque.
- Money is handled with exact arithmetic, `decimal.Decimal` in Python and
  integer cents in the browser, and printed to the cent with no floating point
  artifacts.

## Repository layout

```
payroll-ops-toolkit/
  LICENSE
  README.md
  01-payroll-run-calculator/
  02-net-pay-dashboard/
```

## Privacy

The browser tool runs entirely in your browser. Files you load are read with the
`FileReader` API and stay on your machine.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
