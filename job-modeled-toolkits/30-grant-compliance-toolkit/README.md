# Grant Drawdown and Compliance Toolkit

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a grants or award compliance analyst does, tracking
how an award is drawn down, keeping disallowed costs out, and watching the run rate and
the reporting deadlines, while strengthening my foundational software development skills.

This toolkit has two tools. A command-line Python engine walks the award period by
period, draws down only allowable costs, and projects where the spend is heading by the
award end, with a category summary and a reporting-deadline status. A browser view plots
that timeline against the award, with a budget-versus-actual bar per category and the
deadlines listed. Each tool is self-contained and rule-based, with the rules written out
in its own `spec.md`, and there is no framework, no build step, and no server. The sample
data is synthetic, seeded so the grant starts on track and trends over budget.

## The tools
1. **[Grant engine](01-grant-engine/)** command-line Python that reads the award, the
   transactions, and the reporting schedule and writes the drawdown timeline.
2. **[Grant timeline view](02-grant-timeline/)** a browser view that plots the drawdown
   and the run-rate projection against the award, with category bars and deadlines.

## How they connect

The engine writes `timeline.csv` (and a category and a deadline file). The view reads the
timeline (copies ship with it so it renders on its own) and draws the chart, the category
bars, and the deadline list. The shared hand-check runs the whole way through: a 250,000
award that has drawn 100,000 by period 4 at a 25,000 burn rate, so the run rate projects
300,000.00 at the award end, 50,000.00 over, with a 5,000.00 disallowed cost excluded and
one report overdue. The engine's `unittest` suite and the view's `tests.html` both confirm
these numbers to the cent.

## Running the tools

Python 3 runs the engine. The view needs only a browser.

```
# 01 grant engine
python -m unittest
python cli.py --months 12
```

Open `02-grant-timeline/index.html` in a browser for the view, and
`02-grant-timeline/tests.html` for its test page. Each tool folder has its own README and
`spec.md`.

## Repository layout
```
30-grant-compliance-toolkit/
  LICENSE
  README.md
  01-grant-engine/
  02-grant-timeline/
```

## License
Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
