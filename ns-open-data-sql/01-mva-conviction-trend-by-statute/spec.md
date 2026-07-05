# Spec

## Purpose

Take a pinned snapshot of Nova Scotia convictions for two selected Motor Vehicle Act offences and produce one deterministic table that answers three things: how the offences rank against each other within each year, how each offence changed year over year, and which offence rose or fell fastest across the whole window.

## Inputs

Dataset: Convictions for Select MVA Offences (`uvv7-hnbr`), pulled to `data/raw/ns_mva-conviction-trend_2026-07-05.csv`. See SOURCE.md.

Columns used (all four): `offence_statute`, `description`, `year_convicted`, `convictions`.

## Cleaning and validation rules (02_transform.sql)

1. Trim whitespace from `offence_statute` and `description`.
2. Cast `year_convicted` and `convictions` from text to integer.
3. Drop any row where `offence_statute`, `year_convicted`, or `convictions` is null or blank.
4. Collapse to one row per (`offence_statute`, `description`, `year_convicted`) by summing `convictions`. The source already holds one row per offence-year, so this is a guard: it stops a stray duplicate from double-counting or from making the window functions non-deterministic.

## Analysis logic step by step (03_analysis.sql)

The build runs three tables plus a headline table.

**offence_window** (one row per offence). Groups the clean yearly rows by offence and reads the endpoints of the window:

- `first_year` = `MIN(year_convicted)`, `last_year` = `MAX(year_convicted)`.
- `first_convictions` = `arg_min(convictions, year_convicted)`, the count at the earliest year.
- `last_convictions` = `arg_max(convictions, year_convicted)`, the count at the latest year.

**offence_window_ranked** (one row per offence). Adds the window measures and the cross-offence ranking:

- `window_change` = `last_convictions - first_convictions`.
- `window_pct_change` = `round(100.0 * window_change / first_convictions, 1)`, a percent. Percent is used because it is comparable across offences of very different volume (thousands of cellphone convictions versus tens of school bus convictions).
- `window_trend` = `rising` when `window_change > 0`, `falling` when `< 0`, else `flat`. The sign of the net first-to-last change equals the sign of the average year-over-year change, so this labels the net direction across the window.
- `window_rank` = `DENSE_RANK() OVER (ORDER BY window_pct_change DESC)`. Rank 1 is the fastest riser; the largest rank is the fastest faller.

**convictions_ranked** (one row per offence-year, the exported table). Joins each yearly row to its offence window summary and adds:

- `rank_in_year` = `DENSE_RANK() OVER (PARTITION BY year_convicted ORDER BY convictions DESC)`. Within each year, ranks the offences by conviction count.
- `prev_convictions` = `LAG(convictions) OVER (PARTITION BY offence_statute ORDER BY year_convicted)`. The offence's own count in the prior year.
- `yoy_change` = `convictions - prev_convictions`.
- `yoy_pct_change` = `round(100.0 * yoy_change / prev_convictions, 1)`.

**headline** (two rows). Reads `offence_window_ranked` and writes two ready-to-print lines naming the fastest-rising offence (minimum `window_rank`) and the fastest-falling offence (maximum `window_rank`). `run.py` prints these; it does not compute them.

## Outputs

`out/convictions_ranked.csv` (generated) and `expected/convictions_ranked.csv` (golden, committed). One row per offence-year, 28 rows. Every column is defined in data_dictionary.md. Each row is one offence in one year, carrying that year's within-year rank and year-over-year move plus the offence's whole-window summary and cross-offence rank.

Row order is fixed by `ORDER BY window_rank, offence_statute, year_convicted` in 99_export.sql: the fastest-rising offence's fourteen years come first, oldest to newest, then the next offence.

## Edge cases

- **First observed year:** there is no prior year, so `prev_convictions`, `yoy_change`, and `yoy_pct_change` are null for the earliest row of each offence. They render as empty fields in the CSV.
- **Ties in a ranking:** `DENSE_RANK` gives tied values the same rank. The current snapshot has no ties in either `rank_in_year` or `window_rank`.
- **Blank or non-numeric source cells:** removed in cleaning before any arithmetic runs.
- **Duplicate offence-year rows:** summed away in `mva_yearly` so a duplicate cannot skew a count or a rank.

## Determinism

The snapshot is pinned and committed. Every result query ends in an `ORDER BY`, and percents are rounded to one decimal, so the same input always produces byte-identical output. `expected/convictions_ranked.csv` was built from a first verified run; `run.py` re-runs the pipeline and diffs the fresh output against it, printing PASS only on an exact row-for-row match.
