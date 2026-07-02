# IT Cost Allocation and Showback Toolkit

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work an IT finance or showback analyst does, splitting
shared technology costs across the departments that use them, while strengthening my
foundational software development skills.

This toolkit has two tools across two languages. A command-line Python engine splits a
pool of shared IT costs across departments by a driver such as headcount, tying every
split back to the pool to the cent. A second Python tool uses `openpyxl` to turn that
allocation into a formatted Excel workbook whose allocation cells are live formulas,
then verifies the workbook's formulas reproduce the engine's numbers to the cent. Each
tool is self-contained and rule-based, with the rules written out in its own `spec.md`,
and there is no framework, no build step, and no server. The sample data is synthetic.

## The tools
1. **[Allocation engine](01-allocation-engine/)** command-line Python that splits the
   cost pool across departments by driver and writes the allocation matrix.
2. **[Chargeback workbook builder and verifier](02-chargeback-workbook/)** a Python tool
   that builds a formatted Excel workbook with live formulas from the matrix, plus a
   verifier that checks every formula against the engine to the cent.

## How they connect

The engine writes `allocation_matrix.csv`. The workbook builder reads it and writes
`chargeback_workbook.xlsx`, putting the department drivers in as values and each
allocation in as a live Excel formula. The verifier then reads the workbook back and,
using its own small formula evaluator rather than Excel or the engine, confirms every
formula computes the engine's figure to the cent. The shared hand-check is a 100,000
pool split by headcount: Engineering takes 40 percent, 40,000.00 in all, and the four
departments sum back to the 100,000.00 pool. The engine's `unittest` suite and the
workbook verifier (50 checks) both confirm it.

## Running the tools

Python 3 runs the engine. The workbook tool also needs `openpyxl`.

```
# 01 allocation engine
python -m unittest
python cli.py

# 02 chargeback workbook builder and verifier
python -m pip install -r requirements.txt
python build_workbook.py
python verify_workbook.py
```

Each tool folder has its own README and `spec.md`.

## Repository layout
```
28-it-cost-allocation-toolkit/
  LICENSE
  README.md
  01-allocation-engine/
  02-chargeback-workbook/
```

## License
Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
