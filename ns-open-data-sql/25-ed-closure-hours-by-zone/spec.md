# Spec: emergency department closure hours by zone

## Purpose

Turn the province's emergency department closure hours table into a result that
answers three questions: how many hours each zone, facility type, and site
reported over twelve fiscal years, how those hours split between temporary and
scheduled closures, and how each zone moved year over year. Every figure is
deterministic and re-derivable from the committed snapshot.

## Inputs

One file: `data/raw/ns_ed-closure-hours_2026-07-25.csv`, a pinned snapshot of
Socrata dataset `75nx-yut7` (see SOURCE.md). Columns: year, zone, type, site,
temporary, scheduled, total. 456 rows, which is 38 sites reporting in each of
twelve fiscal years from 2012-13 to 2023-24.

## Named rules

Every rule below is a named constant or a named macro in `sql/00_schema.sql`, so
none of them is buried inside an expression somewhere downstream.

1. **`fiscal_year_start(label)`.** The `year` column holds a fiscal string like
   `2023-24`, which sorts as text but not as a year. The first four characters
   are the starting calendar year, so `2023-24` gives `2023`. Every ordering,
   every `LAG`, and the whole BI layer use that integer; nothing sorts on the
   label. It is carried in the golden output and in the mart so Power BI never
   has to derive it in Power Query.
2. **`canonical_site(raw)`.** Trim, collapse internal runs of spaces, then fold
   the curly apostrophe (U+2019) to the ASCII one. The portal switched
   apostrophe style at the 2018-19 to 2019-20 boundary, which splits
   Fishermen's Memorial Hospital, St. Martha's Regional Hospital, and
   St. Mary's Memorial Hospital into two facilities each.
3. **`rule_site_rename`.** One explicit entry: `Roseway` becomes
   `Roseway Hospital`. That is a rename of the same facility, not a punctuation
   difference, so it is written out by hand rather than folded by a pattern. No
   fuzzy matching is used anywhere; a rename either has a row in this table or
   it does not happen.
4. **`temporary_share_pct(temporary, total)`.** The denominator is the reported
   `total` column, guarded so it is above zero. See below.
5. **`change_pct(current, previous)`.** Same guard, same rounding, used for the
   year-over-year percent.
6. **`fiscal_year_pattern` and `hours_pattern`.** A row whose fiscal label or
   hours values do not match these is counted as an excluded row rather than
   parsed into a NULL. Both patterns match every row in this snapshot, so the
   exclusion counts are all zero, but the check is what makes that a stated
   result rather than an assumption.

## The temporary share denominator

Temporary share is `temporary / total`, where `total` is the column the portal
reports, not `temporary + scheduled` recomputed. The two are the same on every
row in this snapshot, and the reconciliation check below is what proves it. The
division is guarded so the denominator must be above zero; where the guard
fires, the share is blank rather than zero, because a facility with no closures
has no split to report, not a split of nothing. The guard fires on 238 of the
456 site-years.

## The reconciliation check

Before any aggregation, `03_analysis.sql` computes
`temporary + scheduled - total` for all 456 rows and reports four figures in the
`reconciliation` section of the golden file:

| Measure | Value in this snapshot |
| --- | --- |
| `rows_checked` | 456 |
| `rows_reconciled` | 456 |
| `rows_mismatched` | 0 |
| `mismatch_total_abs_hours` | 0.0 |
| `mismatch_max_abs_hours` | 0.0 |

Both the count and the magnitude are exported. A future snapshot that broke the
identity would show up as a nonzero count with the size of the break beside it,
rather than as a quietly wrong share.

## Row accounting

No row is ever silently dropped. `02_transform.sql` tags every raw row with
either nothing or exactly one named exclusion reason, and the `row_accounting`
section of the golden file publishes the ledger:

| Measure | Value |
| --- | --- |
| `rows_in_snapshot` | 456 |
| `rows_excluded_unparsable_fiscal_year` | 0 |
| `rows_excluded_unparsable_hours` | 0 |
| `rows_excluded_missing_site` | 0 |
| `rows_excluded_missing_zone_or_type` | 0 |
| `rows_loaded_clean` | 456 |

The snapshot row count minus the four exclusion classes equals the clean row
count, and that identity can be read off the file itself.

## Analysis steps (03_analysis.sql)

1. `recon_check` and `recon_summary`: the identity check described above.
2. `grand_total`: hours, counts, and the provincial temporary share.
3. `zone_totals`: hours by zone across all twelve years.
4. `type_totals`: hours by the facility type reported in each site-year.
5. `site_totals`: all 38 sites ranked by total closure hours, each with its own
   temporary share.
6. `zone_year`: zone by fiscal year, with the change against the previous year
   taken by `LAG (total_hours) OVER (PARTITION BY zone ORDER BY fiscal_year_start)`.
7. `ed_closures`: the seven sections stacked into one file with a fixed sort key.
8. `mart_ed_closures`: one cleaned row per source site-year, 456 rows, exported
   for the Power BI face and for the browser dashboard.

## Outputs

- `out/ed_closures.csv`, diffed line for line against `expected/ed_closures.csv`.
  128 lines including the header.
- `out/mart_ed_closures.csv`, copied to `bi/exports/mart_ed_closures.csv`: the
  site-year mart, 456 rows, summing to the same 520,811.3 hours.
- `dashboard/data.js`: the same mart rows re-emitted as a `const DATA` array so
  the dashboard opens under `file://` with no server and no file picker.

## The dashboard re-derivation

`dashboard/data.js` is plumbing: it holds the mart rows and no figures. Every
number the page shows is computed in `dashboard.js` from those rows, and the
results have to equal the SQL golden exactly:

| Figure on the page | Value it must show |
| --- | --- |
| Total closure hours card | 520,811.3 |
| Temporary closure hours card | 217,293.8, 41.72% of all closure hours |
| Scheduled closure hours card | 303,517.5, 58.28% of all closure hours |
| Site-years with no closures card | 238 of 456 |
| Zone list, in order | Zone 3 223,648.9 (36.45% temporary), Zone 1 118,442.9 (54.44%), Zone 4 90,587.7 (44.87%), Zone 2 88,131.8 (34.79%), IWK 0.0 (share not defined) |
| Facility type list, in order | Community 293,479.4 (52.94%), CEC 227,331.9 (27.24%), then Regional, Tertiary, and UTC at 0.0 |
| Ranked site table | 38 rows, top row New Waterford Consolidated Hospital, Zone 3, 65,073.5 hours, 11.51% temporary |

Hours are reported to one decimal place, so the page does its arithmetic on
tenths of an hour as integers. Adding 0.1 values as floating point drifts by the
time you reach half a million hours; adding them as integers does not. The
temporary share uses the same guarded denominator and the same two-decimal
rounding as the SQL.

## Edge cases

- **Zero hours** is a real reading, not a missing one. 238 of the 456 site-years
  report 0.0, and 13 of the 38 sites report zero in all twelve years. Those rows
  stay in every count, every ranking, and the mart. They are counted and
  reported rather than filtered, because "reported no closures" and "did not
  report" are different statements and only one of them is true here.
- **Facility type** is not fixed per site. Eight sites carry two different types
  across the window, all of them a move to UTC in 2021-22, 2022-23, or 2023-24.
  `type_totals` groups on the type reported in that site-year, which is what the
  source rows say. `site_totals` needs one type per site and uses the one
  reported in the site's most recent observed year; site and fiscal year are
  unique together, so that picks exactly one row.
- **Regional, Tertiary, and UTC** site-years report 0.0 hours across the whole
  window, so the entire 520,811.3 hours sits in Community and CEC site-years.
  The zero rows are still exported, with the share left blank rather than set to
  zero.
- **The IWK zone** reports zero in all twelve years, so its year-over-year change
  is 0.0 every year and its temporary share is blank throughout.
- **A zone's first year** has no prior value, so its change fields are blank.
  Every zone reports in all twelve years here, so the `LAG` is always the
  calendar-previous year and no gap-filling question arises.
- **A zero base** leaves the percent change undefined. Where the previous year is
  0.0, `yoy_change_hours` still reports the absolute move and `yoy_change_pct`
  is blank.

## Determinism

Hours run as `DECIMAL(18,1)` end to end, matching the one decimal place the
portal reports; percentages are display values rounded to two decimals after the
exact division. Every ranking is a `row_number()` whose `ORDER BY` ends in a
unique tie-breaker (the zone code, the facility type, or the site name), never a
measure alone. The two `COPY` statements in `99_export.sql` end their `ORDER BY`
with `site, fiscal_year_start`, which is unique in both files, so the exports are
byte-stable run to run and across DuckDB versions. The golden was built from a
first verified run and confirmed by a second run reporting PASS.
