# Data dictionary: out/license_density.csv

One row per community and license type that appears in the snapshot. The file has
706 data rows plus a header. Sorted by `community_total_licenses` descending, then
`community` ascending, then `type_count` descending, then `license_type` ascending.

| Column | Type | Meaning | Units |
|---|---|---|---|
| `community` | text | The community the license belongs to, from a cleaned `city_town`. A blank or missing town appears as `(Unknown)`. | name |
| `community_total_licenses` | integer | Total permanent licenses in this community, across all license types. Repeats on every row for the same community. | count of licenses |
| `community_rank` | integer | The community's rank by `community_total_licenses`, busiest first (1 = most). Communities with equal totals share a rank. | rank |
| `license_type` | text | The license category within the community, cleaned (trimmed, internal whitespace collapsed). For example Eating Establishment, Lounge, Club, Special Premises. | category |
| `type_count` | integer | Licenses of this `license_type` in this `community`. | count of licenses |
| `type_share_pct` | number | `type_count` as a percentage of `community_total_licenses`, rounded to one decimal place. | percent (0 to 100) |
| `is_dominant_type` | integer | 1 if this is the community's single most common license type (ties broken by `license_type` name), otherwise 0. Exactly one row per community carries a 1. | flag (0 or 1) |
