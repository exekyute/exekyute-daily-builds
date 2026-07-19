# Spec

## Purpose

Take a pinned snapshot of the Nova Scotia Open Data portal's own catalogue and produce one deterministic report that answers four things: how many assets sit in each freshness bucket, which categories and which owning departments carry the highest share of stale assets, and which individual public datasets have gone longest without a data update. A per-asset mart feeds the Power BI guide in bi/README.md.

## Inputs

Dataset: Nova Scotia Open Data Catalogue (`3km6-ez4q`), pulled to `data/raw/ns_catalogue_2026-07-06.csv`. See SOURCE.md.

Columns used: `name`, `detailedmetadata_department`, `type`, `category`, `url`, `last_data_updated_date`, `last_metadata_updated_date`. The other three (`description`, `tags`, `api_endpoint`) are loaded but not analyzed.

## The pull-date constant

Staleness is always relative to a date, and using the wall clock would make the output drift every day. So the pull date is declared once in 02_transform.sql as a literal:

    CREATE TABLE params AS SELECT DATE '2026-07-06' AS pull_date;

Every age in the pipeline is measured against `params.pull_date`, never `CURRENT_DATE`. This is what keeps the golden output stable forever.

## Cleaning and validation rules (02_transform.sql)

1. Trim whitespace from `name` and `url`; lowercase `type`.
2. Backfill blank groupings with explicit labels: blank `category` becomes `(uncategorized)` (7 assets in this snapshot), blank department becomes `(no department)` (none in this snapshot).
3. Extract the asset's Socrata 4x4 id (`uid`) from the tail of `url` with a regex. All 1,269 urls yield one.
4. Cast the two Socrata timestamps to dates with `try_cast`, so an unparseable value becomes null instead of failing the run. None fail in this snapshot.
5. Drop rows with a blank `name` (unidentifiable assets). None exist in this snapshot, so 1,269 rows survive cleaning.

## Freshness rule and bucket boundaries

- `last_updated` = `last_data_updated` when present, else `last_metadata_updated`. The data date is the freshness signal; the metadata date is only a fallback. In this snapshot every asset has a data date, so the fallback never fires.
- `age_months` = `date_diff('month', last_updated, pull_date)`: the number of calendar month boundaries crossed between the two dates. Day-of-month is ignored by this rule; an asset updated 2026-06-30 is 1 month old and one updated 2026-07-01 is 0 months old.
- Buckets, with explicit boundaries on `age_months`:

  | Bucket | Rule |
  | --- | --- |
  | Fresh | `age_months < 6` |
  | Aging | `6 <= age_months < 12` |
  | Stale | `12 <= age_months < 24` |
  | Dormant | `age_months >= 24` |
  | No date | `last_updated` is null |

- `stale_or_dormant` = 1 when `age_months >= 12` (the Stale and Dormant buckets), else 0. Assets with no usable date are never counted stale; they are surfaced as their own bucket instead.

## Analysis logic step by step (03_analysis.sql)

**bucket_summary** (five rows, one per bucket). A `VALUES` scaffold pins all five buckets in age order and left-joins the per-bucket counts, so an empty bucket (No date, in this snapshot) still appears with a zero count. Columns: asset count, share of all assets, average age within the bucket.

**by_category** (one row per category). Groups the audit by `category`: asset count, stale-or-dormant count, the percent those represent of the category's own assets, and the category's average age. `row_rank` orders categories by that percent descending, ties broken by asset count then name, so a small category with every asset stale ranks above a large, mostly healthy one.

**by_owner** (one row per owning department). Identical shape to by_category, keyed on `owner`.

**worst_offenders** (15 rows). Assets with `type = 'dataset'` and a usable date, ranked oldest first by `age_months`, ties broken by exact date then name, cut to the top 15. Datasets only: charts, filtered views, and stories are derived from datasets, and external links and calendars are not maintained data, so the list names the assets a publisher is expected to keep current.

**freshness_audit** (80 rows, the exported report). Stacks one `overall` row plus the four tables above into a single table with a shared column set (`section`, `item`, `detail`, `n_assets`, `n_stale_dormant`, `pct`, `age_months`, `last_updated`, `row_rank`), everything cast to VARCHAR so unused cells export as empty fields. Percents and averages are formatted to one decimal with `printf` inside the SQL, which fixes the exported text exactly.

**headline** (two rows). Ready-to-print lines naming the portal-wide stale share and the single oldest maintained dataset. `run.py` prints these; it does not compute them.

## Outputs

- `out/freshness_audit.csv` (generated) and `expected/freshness_audit.csv` (golden, committed): the 80-row stacked report. Row order is fixed by an explicit section order (overall, bucket_summary, by_category, by_owner, worst_offenders) then `row_rank`.
- `out/mart_freshness.csv`, copied by `run.py` to `bi/exports/mart_freshness.csv` (committed): one row per asset with `uid`, `name`, `type`, `category`, `owner`, `last_updated`, `age_months`, `bucket`, `bucket_order`, `stale_or_dormant`. Ordered oldest first, ties broken by name then uid; `uid` is unique, so the order is total.

Every column of both files is defined in data_dictionary.md.

## Edge cases

- **Assets with no update date:** `try_cast` turns unparseable timestamps into nulls, and a null `last_updated` lands the asset in the No date bucket with empty `age_months`. It is excluded from the stale-or-dormant numerator and from the worst-offenders list, but stays in every denominator as a visible bucket. This snapshot has zero such assets; the rule exists so a future snapshot cannot silently break the audit.
- **Future-dated updates:** an update timestamp after the pull date would produce a negative `age_months`, which lands in Fresh. None exist in this snapshot.
- **Blank category or department:** relabeled `(uncategorized)` and `(no department)` so the rollups keep every asset instead of dropping a group key.
- **Ties in rankings:** every `ROW_NUMBER` ordering ends in a unique key (name, then uid where needed), so ranks never depend on scan order.

## Determinism

The snapshot is pinned and committed. Ages are measured against the literal pull date, never the wall clock. Every result query ends in an `ORDER BY` that reaches a unique key, and every percent or average is fixed to one decimal by `printf` in the SQL. The same input therefore always produces byte-identical output. `expected/freshness_audit.csv` was built from a first verified run; `run.py` re-runs the pipeline and diffs the fresh output against it, printing PASS only on an exact row-for-row match.
