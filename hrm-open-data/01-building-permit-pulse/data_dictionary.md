# Data dictionary: pipeline outputs

Three result files plus the frozen mart. The mart is documented separately in
`bi/exports/data_dictionary.md`, since it is the file the BI tools and the
dashboard read.

## out/permits_by_year_worktype.csv (golden)

One row per issue year and work type. 19 rows over 2020 to 2026 and the three work
types. Only permits with an issuance date are counted.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `issue_year` | integer | Calendar year the permit was issued. |
| 2 | `work_type` | text | New Building, Renovation, or Addition. |
| 3 | `permit_count` | integer | Permits issued in that year and work type. |
| 4 | `total_project_value` | number | Sum of declared project value, dollars to the cent. A missing value counts as zero. |
| 5 | `total_net_new_units` | integer | Sum of net new residential units; can be negative. |

## out/district_units_running_total.csv (golden)

One row per district and issue year. 104 rows over the 17 districts and the years
each district has permits in. Ordered by district then year.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `district` | text | Council district (District 01 to District 16, or Unidentified). |
| 2 | `issue_year` | integer | Calendar year the permits were issued. |
| 3 | `net_new_units` | integer | Net new residential units in that district and year. |
| 4 | `cumulative_net_new_units` | integer | Running total of `net_new_units` within the district, oldest year to newest. |

## out/permits_by_community.csv (dashboard feed)

One row per community over all issued permits, ranked by declared value. Not a
golden; it feeds the browser dashboard's community ranking.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `community` | text | Community name; a blank community is `(Unspecified)`. |
| 2 | `permit_count` | integer | Permits issued in the community. |
| 3 | `total_project_value` | number | Sum of declared project value, dollars to the cent. |
| 4 | `total_net_new_units` | integer | Sum of net new residential units. |

Notes:

- The 2,470 permits with no issuance date are excluded from all three files but
  remain in the per-permit mart.
- `total_project_value` summed across the year-and-work-type rows equals the same
  total summed across the community rows: 18,683,679,885.12 dollars.
