# AI Operations Toolkit

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work an AI operations analyst does, running the cost,
quality, and reporting side of a company's AI program, while strengthening my
foundational software development skills.

The toolkit holds three tools in three languages: a Python command-line cost engine, a
SQL model scorecard on SQLite, and a browser dashboard built with plain HTML, CSS, and
JavaScript. They are self-contained and rule-based, with the rules written out in each
tool's spec, and they run with no framework, no build step, and no server. The sample
data is synthetic, seeded so a single run of each tool exercises every branch.

## The tools
1. **[LLM cost engine](01-llm-cost-engine/)** prices a month of LLM usage, allocates a
   shared cost pool across teams with the largest-remainder method, checks each team
   against its budget, and forecasts month-end spend. Python, standard library only.
2. **[Model scorecard](02-model-scorecard/)** scores and ranks the models for one task
   on accuracy, precision, recall, F1, latency, and cost, and reconciles team spend
   against the cost engine. SQL on SQLite with a Python runner.
3. **[AI operations dashboard](03-ai-ops-dashboard/)** lays out spend against budget,
   the month-end forecast, and the ranked scorecard on one page. Browser tool.

## How they connect
The cost engine writes `cost_by_call.csv`, `cost_by_model.csv`, and `cost_by_team.csv`.
The scorecard runner reads `cost_by_call.csv`, re-aggregates the per-call costs in SQL,
and confirms the grand total of **$775.85** and every team total match the engine to
the cent. It also writes `model_scorecard.csv`. The dashboard reads the engine's
`cost_by_team.csv` and the runner's `model_scorecard.csv` and shows a loaded-spend total
of **$1,615.85** ($775.85 of direct usage plus an $840.00 shared pool), the same figures
the other two tools produce.

## Running the tools
Python 3 is the only requirement, and it is standard library throughout. From the
toolkit folder:

```
cd 01-llm-cost-engine
python -m unittest          # run the cost engine tests
python cli.py               # price the sample usage and write the CSV outputs

cd ../02-model-scorecard
python runner.py            # score the models and reconcile the spend

cd ../03-ai-ops-dashboard
# open index.html in a browser, or open tests.html to run the dashboard tests
```

Each tool folder has its own README and `spec.md` with the full rules, the input and
output formats, and the hand-checked numbers.

## Repository layout
```
24-ai-operations-toolkit/
  LICENSE
  README.md
  01-llm-cost-engine/
  02-model-scorecard/
  03-ai-ops-dashboard/
```

## License
Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
