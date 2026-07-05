# Data dictionary: out/convictions_ranked.csv

One row per offence per year. 28 rows over two offences and the years 2011 to 2024. The first eleven columns describe the offence-year; the last six repeat that offence's whole-window summary on every one of its rows.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `window_rank` | integer | Rank of this offence among all offences by `window_pct_change`, highest first. 1 is the fastest riser over the window; the largest value is the fastest faller. | rank (1 = top) |
| 2 | `window_trend` | text | Net direction of the offence across the window: `rising`, `falling`, or `flat`. | category |
| 3 | `offence_statute` | text | Motor Vehicle Act section code for the offence. | code |
| 4 | `description` | text | Plain-language description of the offence. | text |
| 5 | `year_convicted` | integer | Calendar year the convictions were recorded. | year |
| 6 | `convictions` | integer | Convictions for this offence in this year. | count |
| 7 | `rank_in_year` | integer | Rank of this offence among all offences in the same year by `convictions`, highest first. | rank (1 = top) |
| 8 | `prev_convictions` | integer | This offence's convictions in the prior year. Empty for the offence's first observed year. | count |
| 9 | `yoy_change` | integer | `convictions` minus `prev_convictions`. Empty for the first observed year. | count |
| 10 | `yoy_pct_change` | number | Year-over-year change as a percent of `prev_convictions`, one decimal. Empty for the first observed year. | percent |
| 11 | `first_year` | integer | Earliest year observed for this offence. | year |
| 12 | `last_year` | integer | Latest year observed for this offence. | year |
| 13 | `first_convictions` | integer | Convictions in `first_year`. | count |
| 14 | `last_convictions` | integer | Convictions in `last_year`. | count |
| 15 | `window_change` | integer | `last_convictions` minus `first_convictions`. | count |
| 16 | `window_pct_change` | number | `window_change` as a percent of `first_convictions`, one decimal. | percent |

Notes:

- Columns 1, 2, and 11 through 16 hold the same value on every row of a given offence, since they describe the offence over the whole window, not the single year.
- Empty cells in columns 8, 9, and 10 mark the first year of an offence, where no prior year exists to difference against.
