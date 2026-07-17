# Data dictionary

## expected/key_figures.csv

One row per key figure, in Model-sheet cell order. Columns:

| Column | Type   | Meaning                                      |
|--------|--------|----------------------------------------------|
| figure | text   | Snake-case figure name, mapped to its Model sheet cell in spec.md |
| value  | text   | The figure's value as written by Python: money as a plain number with two decimals (no separators), counts as integers, the percentage as a decimal fraction |

The figures themselves:

| figure                      | Type  | Units | Meaning                                                                 |
|-----------------------------|-------|-------|-------------------------------------------------------------------------|
| raise_pct                   | input | fraction | The raise percentage the verification pins, 0.02 = 2%                |
| classification_count        | count | classifications | Distinct pay plans in the current scale period                 |
| published_rate_count        | count | rates | Published step rates across all classifications                         |
| total_biweekly_base         | money | CAD per biweekly pay period | Sum of every published biweekly rate            |
| raise_total                 | money | CAD per biweekly pay period | Cost of raising every published rate by raise_pct, summed from per-classification costs |
| raise_top_classification    | text  |       | Classification with the largest raise cost (first alphabetically on a tie) |
| raise_top_cost              | money | CAD per biweekly pay period | That classification's raise cost                |
| single_step_classifications | count | classifications | Classifications with exactly one published step                |
| widest_span                 | money | CAD per biweekly pay period | Largest first-step-to-top-step span             |
| widest_span_classification  | text  |       | Classification with that span (first alphabetically on a tie)           |

All money figures are biweekly amounts in Canadian dollars on the published
scale, per the headcount-free assumption in spec.md.

## Model sheet blocks

| Block | Location | Meaning |
|-------|----------|---------|
| Inputs | A4:B5 | The raise-percentage input cell (B5), default 2.0%, shaded as the one cell meant to be edited |
| Key figures | A7:B16 | The ten figures above as live formulas, labelled in column A |
| Pay-band grid | row 18 down, columns B onward | One row per classification, one column per progression step (Step 1 = the plan's lowest rate), published biweekly rate at each intersection |
| Derived columns | right of the step columns | Steps, First step, Top step, Span, One-step cost, Base total, Raise cost; all live formulas per classification row |

## Model sheet derived columns

| Column | Type | Units | Meaning |
|--------|------|-------|---------|
| Steps | count | steps | Published steps for the classification |
| First step | money | CAD biweekly | Lowest-step rate (MIN; rates never fall along the progression) |
| Top step | money | CAD biweekly | Top-step rate (MAX) |
| Span | money | CAD biweekly | Top step minus first step |
| One-step cost | money | CAD biweekly | Span divided by (Steps - 1), rounded to the cent; 0.00 for single-step classifications |
| Base total | money | CAD biweekly | Sum of the classification's published rates |
| Raise cost | money | CAD biweekly | SUMPRODUCT(ROUND(rate x raise, 2)) across the classification's steps |

## Data sheet

The cleaned long-format scale, one row per published rate, in progression
order inside each classification:

| Column | Type | Units | Meaning |
|--------|------|-------|---------|
| classification | text | | pay_plan from the source dataset |
| step | integer | | Progression position, 1 = the plan's lowest rate; matches the Model sheet's Step columns |
| step_label | integer | | pay_plan_level as published on the portal (EC, LM, and SO plans label their below-range steps 80 to 99 ahead of label 0) |
| biweekly_rate | money | CAD per biweekly pay period | Published biweekly rate at that step |
