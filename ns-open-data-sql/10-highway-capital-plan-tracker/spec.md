# Spec

## Purpose

Turn Nova Scotia's published Highway Improvement Plan (roads and bridges) into
a formula-driven Excel workbook: county-by-year project pivots, the
project-type mix, and planned road kilometres per fiscal year, with every key
figure verified against a plain-Python recomputation.

## Inputs

- Snapshot: `data/raw/ns_highway-improvement-plan_2026-07-06.csv` (see
  SOURCE.md for how the two underlying datasets were combined).
- Columns used: `project_de`, `county`, `construct_`, `year_start`, `km`,
  `status`, `source`. Ignored: `project_ty` (repeats `construct_` with a
  fiscal year baked into the label), `year_end` (equal to `year_start` on
  almost every row).

## Cleaning rules

Applied by `load_rows()` in build.py, in this order:

1. Trim leading and trailing whitespace on every text field.
2. `county`, `construct_`, `status`: blank after trimming becomes
   `Unspecified`. (The snapshot has no blanks; the rule is a guard.)
3. `construct_`: the two rows labelled `Gravel Roads Program` are folded into
   `Gravel Road Program` (130 rows), the same program under two spellings.
4. `year_start`: blank after trimming becomes `Unknown`. The fiscal-year label
   is otherwise kept exactly as published (for example `2025-2026`).
5. `km`: parsed as a decimal number when present; bridges rows carry no
   length and stay empty.
6. No rows are dropped and no values are otherwise rewritten.

## Model logic, step by step

1. The Data sheet holds the cleaned rows, one per planned project, in snapshot
   order: `source`, `project`, `county`, `type`, `year`, `km`, `status`.
2. The county matrix counts projects with
   `COUNTIFS(county range, row county, year range, column year)`, one row per
   county (alphabetical), one column per fiscal year (ascending). Row totals,
   column totals, and the grand total are SUM formulas over the matrix.
3. The type-mix block does the same with the `type` column, plus a `share`
   column per type: `ROUND(type total / COUNTA(source range), 4)`.
4. The road-kilometre block computes
   `ROUND(SUMIFS(km range, year range, fiscal year, source range, "roads"), 2)`
   per fiscal year; the block total is a SUM over the rounded per-year cells,
   so the block ties exactly by construction.
5. The headline block derives everything from those blocks: total projects
   (`COUNTA` over the source column), leading county
   (`INDEX/MATCH(MAX(...))` over the county-matrix total column), its count
   (`MAX`), largest project type and its share (same pattern over the
   type-mix block), and the roads/bridges split (`COUNTIFS`).
6. build.py recomputes every one of those figures in plain Python from the
   same snapshot and diffs the result against `expected/key_figures.csv`.

There is no Inputs block: the plan is a fixed published document and no
scenario input changes what the tracker reports.

## Cell map

Every key figure in `expected/key_figures.csv`, tied to its Model sheet cell.

| Metric | Model sheet cell(s) |
| --- | --- |
| `total_projects` | `B4` |
| `leading_county` | `B5` |
| `leading_county_projects` | `B6` |
| `top_type` | `B7` |
| `top_type_share` | `B8` |
| `projects_by_source` | `B9` (both counts in one label) |
| `projects_by_county` | `I12:I29`, the county-matrix total column; counties alphabetical down `A12:A29` |
| `projects_by_year` | `B30:H30`, the county-matrix total row; fiscal years ascending across `B11:H11` |
| `type_share_overall` | `J33:J49`, the type-mix share column; types alphabetical down `A33:A49` (counts in `I33:I49`) |
| `road_km_by_year` | `B53:B59`, one row per fiscal year down `A53:A59` |
| `road_km_total` | `B60` |

The county matrix body is `B12:H29` and its grand total `I30` ties to `B4`.
The type-mix body is `B33:H49` with its own total row on row 50.

## Edge cases

- Ties for leading county or largest type break to the first name in
  alphabetical order, because `MATCH` finds the first occurrence in the
  alphabetically sorted block and the Python recomputation scans the same
  sorted order.
- Bridges rows have no `km`; they are excluded from the kilometre block by the
  `source = "roads"` condition, and empty `km` cells contribute nothing to
  `SUMIFS`.
- A blank county, type, status, or fiscal year would surface as `Unspecified`
  or `Unknown` rather than vanishing from the pivots.
- Two published labels are odd but kept as-is: one row starts in fiscal year
  `2024-2024` (almost certainly `2024-2025`, but the model does not guess),
  and one type is labelled `Asphalt Projects for 2026-27` with the year baked
  into the label. Each gets its own pivot row or column, so nothing is
  silently merged.

## Determinism

The build is deterministic: the snapshot is pinned, rows keep snapshot order,
pivot rows and columns are sorted alphabetically or ascending, and there is no
scenario input to pin. Kilometre and share figures are rounded
half-away-from-zero with `decimal.Decimal` and `ROUND_HALF_UP`, matching
Excel's `ROUND`; build.py never touches Python's built-in `round()`, which
rounds half to even. Kilometre totals tie exactly because the total sums the
already rounded per-year figures, in the workbook and in the recomputation.
