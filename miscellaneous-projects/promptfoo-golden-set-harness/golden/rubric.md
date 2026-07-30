# Rubric

The rules a response is scored against. `harness/scoring.py` is the implementation, and
where this file and the code disagree, the code is the one that produced the numbers.

## The schema

Nine fields, extracted from one freight document per case.

| Field | Type | Rule |
|---|---|---|
| `shipment_id` | text | The shipment reference or booking number, as printed. |
| `carrier_scac` | text | Two to four letters. A carrier's name is not a SCAC. |
| `container_id` | text | Four letters then seven digits, ISO 6346 shape. |
| `gross_weight_kg` | number | Kilograms, one decimal. |
| `incoterm` | enum | One of EXW, FCA, FAS, FOB, CFR, CIF, CPT, CIP, DAP, DPU, DDP. |
| `port_of_loading` | text | The five-character UN/LOCODE when the document prints one, otherwise the port name. |
| `ship_date` | date | The on board or sailed date, ISO 8601. An issue date is not a ship date. |
| `declared_value_usd` | number | USD, two decimals. |
| `hazmat` | boolean | True when dangerous goods are declared. |

## Normalization, applied before any comparison

Formatting is not scored. Meaning is. Both sides of every comparison run through the
same normalizer, so a model is never marked wrong for punctuation or letter case.

| Field | Accepted variants that all score the same |
|---|---|
| `container_id` | `MRDU4419078`, `mrdu 441907-8`, `MRDU-4419078` |
| `declared_value_usd` | `42300`, `42300.00`, `$42,300.00`, `USD 42,300.00` |
| `gross_weight_kg` | `18420`, `18420.0`, `18,420.00 KG` |
| `incoterm`, `port_of_loading`, `carrier_scac` | any letter case, surrounding whitespace |
| `ship_date` | `2026-02-11`, `2026-02-11T08:30:00Z` |
| `hazmat` | `true`, `"true"`, `"yes"`, `1` |
| any field | `null`, `""`, `"N/A"`, `"not stated"`, `"unknown"`, `"-"` all read as an abstention |

Three choices in there are deliberate and worth stating plainly.

An answer that carries its unit is read for the value it means. `"26455 lb"` in a
kilogram field converts to `11999.8` and scores correct, because the model did read the
document right and only left the unit in the string. A bare `26455` scores wrong,
because as kilograms it is wrong by a factor of two.

Text that means "the document does not say" is an abstention, not a wrong answer.
`"N/A"` where the golden answer is null scores correct. This matters because the whole
point of the fabrication metric is to separate a model that declines from a model that
invents, and penalising the wording would blur the two.

An ambiguous date is invalid rather than guessed. `14/03/2026` is unambiguous because
there is no fourteenth month, so it normalizes to `2026-03-14`. `03/04/2026` could be
either reading, so it scores as a miss instead of silently becoming March 4 or April 3.

Rounding is half up, to one decimal for weight and two for money.

## The four numbers

| Metric | Definition |
|---|---|
| Field accuracy | Golden fields matched, over golden fields compared. Partial credit per case. |
| Case pass rate | Responses right on all nine fields, over responses scored. No partial credit. |
| Fabrication rate | Fields the model filled in, over fields the document does not state. Measured only on the three golden fields whose answer is null. |
| Consistency | For each case, the share of repeats that landed on the same normalized answer, averaged over cases. |

Consistency is measured on normalized answers, so a model that reformats the same
answer across runs is not counted as unstable. Only a change in meaning shows up. One
repeat is trivially consistent, which is why the report prints the repeat count beside
the number.

## Case verdicts and regressions

A case gets one verdict per model and prompt version, across all its repeats.

- **pass**, right on every repeat.
- **unstable**, right on some repeats.
- **fail**, right on none.

A regression is a case whose verdict goes from pass to fail or to unstable when the
prompt changes. Becoming unstable counts, because an answer that is right two runs out
of three is not a passing case.

## The golden set is checked first

Every golden value is run through its own normalizer before any response is scored. A
golden value that no rule can normalize is reported as a golden-set defect and the
report exits non-zero, because a broken golden answer marks every model wrong on that
field and reads as a model problem.

That guard exists because the first run of this harness scored zero percent across the
board. The YAML loader had read the unquoted `ship_date` values as date objects rather
than strings, so the correct answer was unrepresentable and all 90 responses "failed"
one field. The dates are quoted now, and the check makes that class of mistake announce
itself.

## Scope

A field-level exact match after normalization is the entire rubric. There is no judge
model and no similarity scoring, which suits nine short values copied off a document and
would not suit free-text output. Fifteen cases is a smoke-test size: enough to catch a
prompt change that breaks a rule, not enough to rank two close models.
