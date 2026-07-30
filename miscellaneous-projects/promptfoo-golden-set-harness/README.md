# promptfoo golden-set harness

Runs a 15-case golden set of freight documents through two prompt versions on three models,
scores every response on nine extracted fields, and reports accuracy, fabrication,
run-to-run consistency, and any case that stopped passing when the prompt changed.
promptfoo does the calling and the per-case assertion; a Python layer rescores the recorded
responses and checks its figures against the ones promptfoo wrote down, which on the
committed run agree across all 270 responses. A second configuration replays written model
behaviour instead of calling an API, so the pipeline runs with no key and no network.

## Quickstart

Needs Node and Python 3. Nothing to install: `npx` fetches promptfoo, and the Python side
is standard library only.

```bash
python -m unittest discover -s tests             # 102 tests over the rubric and report
python harness/report.py runs/offline-baseline.json

# regenerate that run from scratch, no API key needed
npx promptfoo@latest eval -c promptfooconfig.offline.yaml --repeat 3 \
  --no-cache --no-table -o runs/offline-baseline.json

# the same report as a gate on a prompt change
python harness/report.py runs/offline-baseline.json --fail-under 0.90
python harness/report.py runs/offline-baseline.json --fail-on-regression
```

## What it measures

| Metric | Definition |
|---|---|
| Field accuracy | Golden fields matched, over golden fields compared. |
| Case pass rate | Responses right on all nine fields, over responses scored. |
| Fabrication rate | Fields filled in, over fields the document does not state. |
| Consistency | Share of repeats of a case that landed on the same normalized answer. |

Both sides of every comparison run through the same normalizer, so formatting never
decides a score. `MRDU 441907-8` and `MRDU4419078` are one answer, `"26455 lb"` in a
kilogram field converts, and `"N/A"` is an abstention rather than a wrong answer.
`golden/rubric.md` has the full rules.

## The golden set

Fifteen synthetic documents in `golden/golden-set.yaml`, each with a `branch` naming the
failure mode it exists to catch: a weight in pounds, a weight in metric tonnes, an absent
incoterm, a scale ticket that disagrees with the certified VGM, an issue date sitting next
to the on board date, a container number garbled in the scan, a zero declared value, a
carrier named without its SCAC, and fields outside the schema that must be ignored. Every
expected value is derivable from the document text alone. Three of the 135 golden fields
have no answer in the document, which is what makes a fabrication rate measurable, and it
is where the prompt change did its damage.

## What the recorded run shows

`runs/offline-baseline.json` came from the offline configuration, so these figures
describe written fixtures rather than measured model quality. What they demonstrate is the
pipeline: 270 responses scored, four metrics, and a regression caught.

| Model | Field accuracy | Case pass rate | Fabrication | Consistency |
|---|---|---|---|---|
| gpt-oss-120b | 97.0% to 98.5% | 73.3% to 86.7% | 0.0% to 66.7% | 100.0% |
| llama-3.3-70b | 96.3% to 97.8% | 66.7% to 80.0% | 33.3% to 100.0% | 100.0% |
| llama-3.1-8b | 94.8% to 96.5% | 53.3% to 68.9% | 33.3% to 100.0% | 95.6% |

Each pair reads v1 to v2. Version 2 spells out the unit conversions, the VGM precedence, and
which of two dates is the ship date, and it fixes four cases on every model. It also ends
with "Return a value for every field in the schema", the line that repairs omitted keys and,
on the same run, takes away the model's permission to abstain. Two cases stopped passing on
all three models: `BOL-007`, where the carrier is named without a SCAC, and `BOL-009`, where
the container number is unreadable. Both went from a correct null to an invented value, and
on the small model fabrication reached every absent field. Reported as one accuracy figure
the change looks like a plain improvement, which is why fabrication and the per-case
verdicts print beside it.

Consistency separates the models on its own axis. Only `llama-3.1-8b` drifts, on `BOL-006`
and `INV-005`, answering two repeats out of three the same way. Those cases are unstable
rather than passing, and the report counts a case that becomes unstable as a regression:
an answer that is right two runs out of three is not a passing case.

## Running it against Groq

`promptfooconfig.yaml` points the same golden set and rubric at
`llama-3.3-70b-versatile`, `openai/gpt-oss-120b`, and `llama-3.1-8b-instant`. Set
`GROQ_API_KEY` in the environment or a `.env` file, then:

```bash
npx promptfoo@latest eval --repeat 3 --no-cache --no-table -o runs/live.json
python harness/report.py runs/live.json
```

Temperature is pinned at 0 and the run still repeats three times, because temperature 0 is a
request rather than a guarantee on hosted inference and drift between identical calls is one
of the things the report is built to catch.

## Repository layout

| Path | What it holds |
|---|---|
| `promptfooconfig.yaml`, `promptfooconfig.offline.yaml` | The live run and the replayed one. |
| `prompts/`, `golden/` | The two prompt versions, the cases, and the rubric. |
| `harness/scoring.py` | The rubric itself. Pure functions, no I/O. |
| `harness/grader.py`, `harness/replay_provider.py` | The promptfoo assertion and the offline provider. |
| `harness/report.py` | Rescores a run, prints the tables, applies the gates. |
| `fixtures/model-profiles.json` | Written model behaviour the replay provider reads. |
| `runs/offline-baseline.json` | 1.7 MB of promptfoo output, committed unedited. |
| `tests/` | 102 unit tests. |

## Known limits

The offline fixtures are written by hand, not recorded from an API. They exercise the
scoring pipeline and nothing more, and no number the offline configuration produces says
anything about how a real model performs. The live configuration measures models.

Fifteen cases is a smoke-test size: enough to catch a prompt change that breaks a stated
rule, not enough to rank two models that are close. The rubric is field-level exact match
after normalization, which suits nine short values copied off a document and would need a
different approach for free-text output. Three repeats detect drift without measuring how
often a rare deviation happens, which would take many more runs than this does.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
