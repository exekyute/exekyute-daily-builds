# Construction WIP and Job-Cost Toolkit

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a construction job-cost or project accountant
does, while strengthening my foundational software development skills.

This toolkit has three tools across three languages. A command-line Python engine
recognizes revenue by cost-to-cost percent complete and writes a work-in-progress
schedule. A second Python tool uses `openpyxl` to turn that schedule into a
formatted Excel workbook whose derived columns are live formulas, then verifies the
workbook's formulas reproduce the engine's numbers to the cent. An Excel VBA macro
sorts and tidies the workbook inside Excel. Each tool is self-contained and
rule-based, with the rules written out in its own `spec.md`, and there is no
framework, no build step, and no server. The sample data is synthetic, seeded so
one run touches a clean job, an overbilled job, an underbilled job, a completed
job, and a not-started job.

## The tools
1. **[Job-cost engine](01-job-cost-engine/)** command-line Python that turns a list
   of contracts into a WIP schedule: percent complete, earned revenue, gross
   profit, and the over or under billing position for each job.
2. **[WIP workbook builder and verifier](02-wip-workbook/)** a Python tool that
   builds a formatted Excel workbook with live formulas from the schedule, plus a
   verifier that checks every formula against the engine to the cent.
3. **[WIP refresh macro](03-wip-refresh-macro/)** an Excel VBA macro that sorts the
   schedule in place by a column you choose and reports the job counts by billing
   position.

## How they connect

The engine writes `wip_schedule.csv`. The workbook builder reads that file and
writes `wip_workbook.xlsx`, putting the four job inputs in as values and the
derived columns in as live Excel formulas. The verifier then reads the workbook
back and, using its own small formula evaluator rather than Excel or the engine,
confirms every formula computes the engine's figure to the cent. The VBA macro
works on that same workbook inside Excel.

The hand-checked example runs through the whole chain. Job J-1001, a 1,200,000
contract with an 800,000 estimated total cost and 480,000 spent, is 60 percent
complete and has earned 720,000.00. Against 700,000.00 billed it is underbilled by
20,000.00. The engine computes it, and the workbook's `=ROUND(C2*E2/D2,2)` and
`=H2-F2` formulas reproduce it, with the verifier confirming all 141 checks across
the workbook agree to the cent.

## Running the tools

Python 3 is the only requirement for the engine. The workbook tool also needs
`openpyxl`. From each tool's folder:

```
# 01 job-cost engine
python -m unittest
python cli.py

# 02 workbook builder and verifier
python -m pip install -r requirements.txt
python build_workbook.py
python verify_workbook.py
```

The VBA macro in `03` is imported into Excel and run there; see its README for the
steps. Each tool folder has its own README and `spec.md` with the detail.

## Repository layout
```
25-construction-wip-job-cost-toolkit/
  LICENSE
  README.md
  01-job-cost-engine/
  02-wip-workbook/
  03-wip-refresh-macro/
```

## License
Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
