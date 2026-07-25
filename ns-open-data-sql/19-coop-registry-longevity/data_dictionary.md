# Data dictionary

## out/coop_longevity.csv

One row per incorporation decade among co-ops on the registry. The file has 10
data rows plus a header, sorted by `decade` ascending. The committed golden copy
is `expected/coop_longevity.csv`.

| Column | Type | Meaning | Units |
|---|---|---|---|
| `decade` | text | The incorporation decade cohort, the incorporation year floored to its decade: `1930s` through `2020s`. | label |
| `survivors` | integer | Co-ops from this cohort on the registry as of the extract date. Cohort counts sum to 369. | count of co-ops |
| `registry_share_pct` | number | `survivors` as a percentage of the whole registry (369), rounded to one decimal place. | percent (0 to 100) |
| `nonprofit_count` | integer | Survivors in this cohort incorporated as non-profit (`N` in the source). | count of co-ops |
| `forprofit_count` | integer | Survivors in this cohort incorporated as for-profit (`P` in the source). | count of co-ops |
| `nonprofit_share_pct` | number | `nonprofit_count` as a percentage of `survivors`, rounded to one decimal place. | percent (0 to 100) |
| `peak_year` | integer | The incorporation year inside this decade with the most surviving co-ops. Ties go to the earliest year, so exactly one peak per decade. | year |
| `peak_count` | integer | Surviving co-ops incorporated in `peak_year`. | count of co-ops |
| `oldest_age_years` | number | Age of the cohort's earliest incorporation as of the pull date `2026-07-06` (declared once in `sql/02_transform.sql`): days elapsed over 365.2425, rounded to one decimal place. | years |

## bi/exports/mart_coop_longevity.csv

One row per co-op on the registry, the input for the Power BI build in
bi/README.md. The file has 369 data rows plus a header, sorted by
`incorporation_date` ascending, then `registry_id` ascending. It is regenerated
by every `python run.py` (copied from `out/mart_coop_longevity.csv`).

| Column | Type | Meaning | Units |
|---|---|---|---|
| `registry_id` | text | The Registry of Joint Stock Companies identifier, unchanged from the source. Unique across the file. | id |
| `co_op_name` | text | The co-operative's registered name, trimmed, internal whitespace collapsed. | name |
| `town` | text | The mailing-address town, cleaned the same way. A blank town would appear as `(Unknown)`; none does in this snapshot. | name |
| `incorporation_date` | date | The full incorporation date, cast from the source's misnamed `incorporation_year` column. | ISO date |
| `incorporation_year` | integer | The year of `incorporation_date`. | year |
| `decade` | text | The incorporation decade cohort, `1930s` through `2020s`. | label |
| `org_form` | text | `Non-profit` or `For-profit`, mapped from the source's `N`/`P` flag. | category |
| `is_nonprofit` | integer | 1 if `org_form` is `Non-profit`, otherwise 0. | flag (0 or 1) |
| `coop_type` | text | The co-op sector from the source `type` column (HOUSING, SERVICES, AGRICULTURE, and so on), cleaned. | category |
| `age_years` | number | Age as of the pull date `2026-07-06`: days from `incorporation_date` over 365.2425, rounded to one decimal place. | years |
