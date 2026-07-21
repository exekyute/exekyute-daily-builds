# Spec

## Purpose

Take a pinned, pre-aggregated snapshot of Halifax open-data portal usage and
produce two deterministic marts: a monthly usage series and a per-dataset usage
ranking. Together they answer which datasets draw the most traffic and how portal
usage moves over time.

## Inputs

Dataset: Open Data Analytics (`HRM::open-data-analytics`), a 639,108-row big-data
layer rolled up once to `data/raw/hrm_open-data-analytics_2026-07-13.csv`
(14,102 rows, one per dataset and month). See SOURCE.md for the pull and the
verbatim aggregation query.

Columns used (all three): `dataset`, `month_start`, `usage`.

## Cleaning and validation rules (02_transform.sql)

1. Cast `month_start` from text to a real `DATE` and `usage` to an integer; trim
   the dataset name.
2. Drop any row where `dataset`, `month_start`, or `usage` is null or blank.
3. Keep only rows with `usage > 0`. The committed snapshot is a faithful roll-up
   that retains dataset-months with a zero usage total; this rule is the
   analytical decision that a dataset "drew usage" in a month only when its total
   is positive. It does not change any total, since a zero adds nothing, but it
   sets when a dataset first counts and how many distinct datasets a month has.
4. Collapse to one row per (`dataset`, `month_start`) by summing `usage`
   (`oda_month`). The snapshot already holds this grain, so this is a guard: it
   keeps the marts deterministic even if the snapshot were re-cut differently.

## Analysis logic step by step (03_analysis.sql)

The build produces two marts plus a headline table.

**mart_usage_monthly** (one row per month). Groups the clean dataset-month rows
by month:

- `year` = `year(month_start)`.
- `total_usage` = `SUM(usage)`, every dataset's hits in that month.
- `distinct_datasets` = `COUNT(DISTINCT dataset)`, how many datasets drew at
  least one hit that month (a consequence of the `usage > 0` rule above).

**mart_usage_by_dataset** (one row per dataset). Groups by dataset:

- `total_usage` = `SUM(usage)` over the whole window.
- `first_month` = `MIN(month_start)`, `last_month` = `MAX(month_start)`, the
  first and last months the dataset drew usage.
- `usage_rank` = `RANK() OVER (ORDER BY SUM(usage) DESC)`. Rank 1 is the most-used
  dataset. `RANK` is competition ranking: tied totals share a rank and the next
  rank skips, which mirrors the Power BI `RANKX(..., DESC, Skip)` measure so the
  two agree row for row. The current snapshot has no ties.

**headline** (two rows). Reads the two marts and writes two ready-to-print lines:
the total recorded usage across the window with the month count and range, and
the single most-used dataset (the `usage_rank = 1` row). `run.py` prints these; it
does not compute them.

## Outputs

Two golden files, each written to `out/` (generated) and `expected/` (committed),
and frozen to `bi/exports/` for Power BI:

- `mart_usage_monthly.csv`, 136 rows, one per month from 2014-07 to 2025-10.
  Ordered by `month_start`.
- `mart_usage_by_dataset.csv`, 237 rows, one per dataset. Ordered by
  `total_usage` descending, then `dataset`.

Both are defined column by column in `data_dictionary.md`. The `bi/exports/`
copies are byte-for-byte identical to the golden, since 99_export writes them from
the same tables with the same `ORDER BY`.

## Determinism

The snapshot is pinned and committed. Every result query ends in an `ORDER BY`,
and no date arithmetic uses `CURRENT_DATE`: the window endpoints fall out of the
data. `SUM(total_usage)` equals `555050254` in both marts and matches the live
`SUM(Usage)` confirmed against the FeatureServer, so a re-cut snapshot would still
tie. `expected/` was built from a first verified run; `run.py` re-runs the
pipeline and diffs the fresh output against it, printing PASS only on an exact
row-for-row match.

## Edge cases

- **Zero-usage dataset-months:** kept in the snapshot, dropped by the `usage > 0`
  rule before any mart is built. This is why the monthly series begins in 2014-07,
  not 2014-04: the three earliest months in the snapshot carried only zero totals.
- **Ties in the ranking:** `RANK` gives tied totals the same rank; the golden
  breaks the row order by `dataset` name. The current snapshot has no ties.
- **Blank or non-numeric cells:** removed in cleaning before any arithmetic runs.
- **Duplicate dataset-month rows:** summed away in `oda_month` so a duplicate
  cannot skew a total or a rank.
