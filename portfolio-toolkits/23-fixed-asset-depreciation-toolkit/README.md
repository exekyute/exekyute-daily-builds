# Fixed-asset depreciation toolkit

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a Canadian fixed-asset or staff accountant does,
maintaining the asset subledger and running depreciation, while strengthening my
foundational software development skills.

The toolkit is three tools wired into one pipeline around the CRA Capital Cost
Allowance system. The Python engine reads an asset register and writes two
schedules; the SQL tool rebuilds the same rollforward and reconciles to the engine
to the cent; the browser dashboard reads the engine output and lays it out. Each
tool is deterministic and rule-based, with the rules written out in its spec, and
the whole thing runs entirely on your machine with no framework, no build step, and
no server.

## The tools

1. **[CCA depreciation engine](01-cca-depreciation-engine)** - command-line Python.
   Reads the asset register and the opening undepreciated capital cost per class,
   applies the half-year rule, declining-balance CCA by class, and straight-line
   book depreciation, and writes a per-asset schedule and a per-class CCA
   rollforward. Handles disposals with recapture and terminal loss.
2. **[Asset register rollforward](02-asset-register-rollforward)** - SQLite with a
   Python runner. Rebuilds the pool for each class straight from the register,
   applies the same rules, and confirms it ties to the engine output to the cent.
3. **[Fixed-asset dashboard](03-fixed-asset-dashboard)** - browser. Reads the
   engine's per-class file and shows Capital Cost Allowance by class, book-versus-tax
   timing, and the rollforward table.

## How they connect

The engine writes `per_class_cca.csv`. The SQL runner reconciles its independent
rollforward against that file, and the dashboard reads it for display. A worked
example runs through all three: class 8 opens at 10,000.00, takes a 5,000.00
addition subject to the half-year rule, and closes at a UCC of 12,500.00 after
2,500.00 of CCA. The same register produces a recapture of 3,000.00 on a class 10
disposal and a terminal loss of 900.00 on a class 50 disposal. The engine, the SQL
runner, and the dashboard all report these to the cent.

The Capital Cost Allowance rates used are the CRA declining-balance rates for the
2026 tax year, written into the engine and the SQL schema with a dated note.

## License

MIT, copyright Kevin Yu (github.com/exekyute).
