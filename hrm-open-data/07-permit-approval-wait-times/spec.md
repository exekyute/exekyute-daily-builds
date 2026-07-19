# Spec

## Purpose

Take a pinned snapshot of Halifax permit processing records and produce two
deterministic files: a frozen per-permit mart both BI faces read, and a summary
that answers, for each issuance stage and jurisdiction, how many permits are
involved, how much total time they carry, and what a typical permit's wait looks
like as both a mean and a median.

## Inputs

Dataset: PPL&C Permit Processing Times (`HRM::pplc-permit-processing-times`), pulled
to `data/raw/hrm_permit-processing-times_2026-07-09.csv`. See SOURCE.md.

Columns used (five of six; `OBJECTID` is ignored): `Permit_Number`, `Issuance_Stage`,
`Jurisdictional_Breakdown`, `Total_Occurrence`, `Total_Duration`.

## Load (00_schema.sql, 01_load.sql)

`00_schema.sql` drops and recreates the four tables so a re-run starts clean, and
declares the raw landing table with every column typed VARCHAR. `01_load.sql` reads
the committed snapshot with `all_varchar = true` and selects the five needed columns
by name, so the unused leading `OBJECTID` column is dropped at load and no field
depends on type auto-detection.

## Cleaning and validation rules (02_transform.sql)

`pt_mart` is the cleaned, typed mart at the source grain, one row per permit per
issuance stage per jurisdictional breakdown:

1. Trim whitespace from `permit_number`, `issuance_stage`, and
   `jurisdictional_breakdown`.
2. Cast `total_occurrence` to BIGINT and `total_duration` to DOUBLE.
3. Drop any row where `permit_number`, `issuance_stage`, `jurisdictional_breakdown`,
   or `total_duration` is null or blank. Six rows carry a null `total_duration` and
   are dropped, leaving 149,705 rows. A missing duration cannot enter a total, an
   average, or a median.

No de-duplication is applied because none is needed: the `(permit, stage,
jurisdiction)` triple is unique in the snapshot, verified in SOURCE.md.

## Analysis logic step by step (03_analysis.sql)

**processing_summary** (one row per issuance stage and jurisdiction, the exported
summary). Groups the mart by `issuance_stage` and `jurisdictional_breakdown` and
reports:

- `permit_count` = `COUNT(DISTINCT permit_number)`. The mart grain makes one row per
  permit inside a group, so this equals the row count; it is written as a distinct
  count because that is the exact denominator the Power BI Avg Duration per Permit
  measure (`DISTINCTCOUNT`) uses.
- `total_duration` = `round(SUM(total_duration), 3)`.
- `avg_duration_per_permit` = `round(SUM(total_duration) / COUNT(DISTINCT permit_number), 3)`.
- `median_duration` = `round(quantile_cont(total_duration, 0.5), 3)`. `quantile_cont`
  is the deterministic linear-interpolation median at the 0.5 quantile, chosen over a
  tie-breaking percentile so the golden is byte-stable. The mean and the median are
  both kept because the distribution is heavily right-skewed, so they diverge and each
  answers a different question.

**headline** (two rows). Reads a stage-level rollup of the mart and writes two
ready-to-print lines: the average duration per permit for Pre Issuance, and the stage
that carries the most total duration with that total. The rollup sums across the
jurisdictions inside a stage; a permit can appear under more than one jurisdiction in
the same stage, so the stage-level distinct permit count is not the sum of the
per-jurisdiction counts, which is why the headline reads from the rollup rather than
from `processing_summary`. `run.py` prints these lines; it does not compute them.

## Outputs

`out/processing_summary.csv` (generated) and `expected/processing_summary.csv`
(golden, committed). Five rows, one per issuance stage and jurisdiction. Every column
is defined in `data_dictionary.md`. Row order is fixed by
`ORDER BY total_duration DESC, issuance_stage, jurisdictional_breakdown` in
99_export.sql, so the heaviest group lands first.

`bi/exports/mart_processing.csv` (frozen mart, committed). 149,705 rows, one per
permit per stage per jurisdiction, ordered by `permit_number, issuance_stage,
jurisdictional_breakdown`. Columns defined in `bi/exports/data_dictionary.md`. Both
BI faces bind to this file and recompute nothing.

## Edge cases

- **Null duration:** six source rows carry no `total_duration`; they are dropped in
  cleaning before any arithmetic runs.
- **A permit across jurisdictions within a stage:** counted once per jurisdiction in
  `processing_summary` and once overall in the stage rollup, so the headline's stage
  distinct count is smaller than the sum of the group counts. This is expected and is
  the reason the headline does not add the group counts.
- **Skew:** durations range from 0 to about 2,028, so the mean sits well above the
  median in every group. Both are reported rather than one standing in for the other.

## Determinism

The snapshot is pinned and committed. Every result query ends in an `ORDER BY`, the
median uses a deterministic quantile, and every figure is rounded to three decimals,
so the same input always produces byte-identical output. `expected/processing_summary.csv`
was built from a first verified run; `run.py` re-runs the pipeline and diffs the fresh
output against it, printing PASS only on an exact row-for-row match.
