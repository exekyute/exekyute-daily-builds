# Data dictionary: out/str_pressure_index.csv and bi/exports/mart_str_pressure.csv

Both files carry the same table: one row per census division, 18 data rows
plus a header. Sorted by `total_registrations` descending, then `region`
ascending. The out/ copy is the verification target that `python run.py`
diffs against the golden file; the bi/exports/ copy is the committed input
the Tableau guide connects to. The same export step writes both from the same
mart table, so the dashboard reads exactly the numbers the golden diff
verified.

| Column | Type | Meaning | Units |
|---|---|---|---|
| `region` | text | The census division, from `census_division` with the trailing ` CD` stripped (`Halifax CD` becomes `Halifax`). The cleaned names match Nova Scotia's county names. | name |
| `total_registrations` | integer | Registered short-term rentals in this region: the commercial and whole-home categories combined. Traditional tourist accommodations are not included (see `traditional_count`). | count of registrations |
| `pct_of_province` | number | This region's share of all registered STRs in the province (2,556 in this snapshot), rounded to one decimal place. | percent (0 to 100) |
| `rank_by_count` | integer | The region's rank by `total_registrations`, most first (1 = most). Regions with equal totals share a rank; in this snapshot the ranks run 1 through 18 with no ties. | rank |
| `commercial_count` | integer | Registrations in the `commercial_short_term_rental` category, the commercial class under the rule in spec.md. | count of registrations |
| `whole_home_count` | integer | Registrations in the `whole_home_primary_residence` category: hosts renting out the whole home they live in. | count of registrations |
| `traditional_count` | integer | Registrations in the `traditional_tourist_accommodation` category (hotels, motels, inns and similar). Context only; not part of the STR total or the shares. | count of registrations |
| `commercial_share_pct` | number | `commercial_count` as a percentage of `total_registrations`, rounded to one decimal place. | percent (0 to 100) |
| `rank_by_commercial_share` | integer | The region's rank by the rounded `commercial_share_pct`, most commercial first (1 = most). Equal displayed shares share a rank. | rank |
| `dominant_type` | text | The larger of the region's two STR categories: `commercial short-term rental` or `whole-home primary residence`. A tie goes to the alphabetically first name (Digby is the one tie in this snapshot). | category |
