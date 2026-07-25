# Spec: co-op registry longevity

## Purpose

Profile the co-operatives on Nova Scotia's registry by incorporation cohort: how
many of today's registered co-ops date from each year and decade, what share of
the registry each cohort holds, how the non-profit versus for-profit mix shifts
across cohorts, and how old each cohort's oldest survivor is. The headline is the
1930s cohort, still 10 co-ops strong, and the mix flip from all for-profit before
1960 to near 80 percent non-profit in the 1980s and 2020s cohorts.

## Inputs

- **Dataset:** Nova Scotia Co-operatives (`k29k-n2db`), pinned snapshot at
  `data/raw/ns_coop-registry_2026-07-06.csv`, 369 rows. Details in SOURCE.md.
- **Columns used:**
  - `registry_id`: carried through as the row identity; unique across the snapshot.
  - `co_op_name`: the co-operative's registered name.
  - `incorporation_year`: despite the name, a full ISO date (`1998-10-08`). The
    basis for every cohort and age computation.
  - `town`: carried into the mart for context; not part of any cohort key.
  - `non_profit_n_for_profit_p`: `N` or `P`, the organizational form.
  - `type`: the co-op sector (HOUSING, AGRICULTURE, SERVICES, and so on).
- Columns present but unused: `address`, `province_state`, `postal_code`.

## The active rule and the cohort definition

The dataset is an extract of co-operatives **registered as of June 8, 2026**. It
has no status column and carries no dissolved records, so active versus inactive
cannot be computed from a field. The rule this project uses instead:

> A co-op is active if and only if it appears in the snapshot. Every row is a
> survivor; co-ops that dissolved before the extract date are simply absent.

Survivorship is therefore read from the registry side: for each incorporation
cohort, the pipeline reports how many co-ops made it onto today's registry, not
what fraction of the cohort's original incorporations survived (the original
denominators are not in this dataset).

A **cohort** is an incorporation decade: the incorporation year floored to its
decade with integer division, labelled `1930s` through `2020s`. Every row lands
in exactly one cohort because every incorporation date parses.

## Cleaning and validation rules

Applied in `sql/02_transform.sql`:

1. **Dates.** `incorporation_year` is trimmed and cast to `DATE`. All 369 rows
   parse; a malformed date would fail the cast loudly rather than being silently
   dropped or defaulted.
2. **Text fields.** `co_op_name`, `town`, and `type` are trimmed and internal
   runs of whitespace collapse to a single space. A blank or missing town would
   become `(Unknown)`; in this snapshot none does.
3. **Organizational form.** `N` maps to `Non-profit`, `P` maps to `For-profit`,
   anything else would map to `(Unknown)`. The snapshot holds only `N` (241 rows)
   and `P` (128 rows). A companion flag `is_nonprofit` carries 1 or 0.
4. No rows are filtered out. The cleaned table holds the same 369 rows as the
   snapshot, so cohort counts sum back to 369.

## The pull-date constant

`sql/02_transform.sql` declares the pull date exactly once, as a literal:

    CREATE OR REPLACE TABLE params AS
    SELECT DATE '2026-07-06' AS pull_date;

Every age in the pipeline (`age_years` in the mart, `oldest_age_years` in the
cohort table) is days from incorporation to that constant, divided by 365.2425
and rounded to one decimal place. `CURRENT_DATE` is never used, so the output is
identical no matter when the pipeline runs.

## Analysis logic, step by step

Applied in `sql/03_analysis.sql`:

1. **Incorporations by year** (`incorporations_by_year`): group the cleaned rows
   by incorporation year; count the rows and the non-profit and for-profit rows
   in each group.
2. **Cohort profile** (`per_decade`): group by decade; count survivors, count the
   non-profit and for-profit split, and take the earliest incorporation date.
3. **Peak year per decade** (`peak`): from the by-year counts, pick each decade's
   busiest incorporation year with `row_number()`, ties going to the earliest
   year, so exactly one peak per decade.
4. **Assemble the cohort table:** join the pieces and compute
   - `registry_share_pct`: the cohort's survivors divided by the registry total
     (369, computed, not hardcoded), times 100, rounded to one decimal place.
   - `nonprofit_share_pct`: non-profit survivors over cohort survivors, times
     100, rounded to one decimal place.
   - `oldest_age_years`: days from the cohort's earliest incorporation to the
     pull-date constant, over 365.2425, rounded to one decimal place.
5. **Mart** (`mart_coop_longevity`): the cleaned table, one row per co-op, for
   Power BI. Same grain, no aggregation.

## Outputs

`sql/99_export.sql` writes two files:

- `out/coop_longevity.csv`: the cohort table, one row per incorporation decade,
  ordered by decade ascending. This is the golden-checked result; the committed
  copy is `expected/coop_longevity.csv` (10 data rows). Columns are defined in
  data_dictionary.md.
- `out/mart_coop_longevity.csv`: the row-level mart, ordered by incorporation
  date then registry id. `run.py` copies it to `bi/exports/mart_coop_longevity.csv`
  for the Power BI build (bi/README.md).

## Edge cases

- **Missing or malformed incorporation dates.** None exist in this snapshot. If
  one appeared in a future pull, the `CAST` in `02_transform.sql` would error and
  stop the run, which is what a pinned, golden-checked pipeline should do.
- **Ambiguous statuses.** Not applicable: the dataset has no status column. The
  active rule above stands in for it. The original cohort denominators are not in
  this dataset, so no survival rate can be computed.
- **Unexpected organizational forms.** Any value beyond `N` or `P` becomes
  `(Unknown)`, so a future snapshot change surfaces in the output.
- **Decade label ordering.** Labels from `1930s` to `2020s` are all four-digit
  years, so lexicographic `ORDER BY decade` equals chronological order.

## Determinism

The snapshot is pinned, the pull date is a literal constant, every result query
ends in `ORDER BY`, and rounding is fixed at one decimal place.
`expected/coop_longevity.csv` was built from a first verified run;
`python run.py` rebuilds `out/` and diffs it against that golden copy row for
row, printing PASS only on an exact match.
