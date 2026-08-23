# Data dictionary

Two generated files are defined here: the golden result and the BI mart. Source columns are described in SOURCE.md.

## `expected/services_coverage.csv` and `out/services_coverage.csv`

One flat table stacking six sections. A column that does not apply to a section is written blank. 97 rows plus a header.

| Column | Type | Meaning |
| --- | --- | --- |
| `section` | text | Which of the six sections the row belongs to: `summary`, `exclusions`, `region_coverage`, `city_coverage`, `fsa_coverage`, `contact_completeness`. |
| `rank` | integer | Position within the section, unique inside it. Assigned by `ROW_NUMBER` over an ordering that ends in a unique tie-breaker, so a tie on the measure never leaves the order to chance. |
| `measure` | text | The named figure on `summary`, `exclusions`, and `contact_completeness` rows. Blank on the three coverage sections, where the dimension columns carry the identity instead. |
| `region` | text | Nova Scotia Works region. Carried on `region_coverage` and `city_coverage` rows, and on the one `summary` row that names the busiest region. Blank elsewhere. |
| `city_town` | text | Community. Carried on `city_coverage` rows only. |
| `fsa` | text | Forward sortation area, the first three characters of the postal code, uppercased. Carried on `fsa_coverage` rows only. |
| `centres` | integer | The row's count. Number of centres on the three coverage sections, number of centres carrying the channel on `contact_completeness`, and the value of the named figure on `summary` and `exclusions`. |
| `towns` | integer | Distinct communities behind the row. Carried on `region_coverage` and `fsa_coverage`. |
| `providers` | integer | Distinct service provider organizations behind the row. Carried on `region_coverage` and `city_coverage`. |
| `share_pct` | decimal(6,2) | The row's centres as a percentage of all 47, to two decimals. Blank on `summary` and `exclusions`. |

### `summary` rows

| `measure` | Meaning |
| --- | --- |
| `total_centres` | Centres in the snapshot. The denominator for every share. |
| `declared_regions` | Size of the declared `REGION_UNIVERSE` constant. |
| `regions_with_centres` | Declared regions holding at least one centre. |
| `regions_with_zero_centres` | Declared regions holding none. The coverage gap measure. |
| `distinct_towns` | Distinct `city_town` values. |
| `distinct_fsas` | Distinct FSAs, ignoring blanks. |
| `distinct_providers` | Distinct `center_name` values, which are organizations rather than sites. |
| `top_region_centres` | Centres in the rank-1 region. That region's name is in the `region` column of this row. |
| `centres_with_all_channels` | Centres publishing all four declared contact channels. |
| `centres_flagged_total` | Centres carrying at least one exclusion flag. Nothing is dropped; this counts what a stricter build would have lost. |

### `exclusions` rows

| `measure` | Meaning |
| --- | --- |
| `region_not_in_universe` | Centres whose region label is absent from the declared universe. |
| `postal_code_blank` | Centres with no postal code, so no FSA. |
| `postal_code_malformed` | Centres whose first three postal characters fail the letter-digit-letter pattern. |
| `coordinate_out_of_bounds` | Centres whose point falls outside the declared Nova Scotia latitude and longitude window. |

### `contact_completeness` rows

`measure` is the channel name: `email`, `web`, `facebook`, `twitter`. `centres` counts those publishing it and `share_pct` is that count over 47. Published means the field holds a value, not that the address was checked.

## `bi/exports/mart_services.csv` and `out/mart_services.csv`

One row per centre, 47 rows, sorted by region, centre name, town, street address. This is the file Tableau connects to and the file `dashboard/data.js` is generated from.

| Column | Type | Meaning |
| --- | --- | --- |
| `region` | text | Nova Scotia Works region, one of the five declared labels. |
| `center_name` | text | The service provider organization. Repeats across sites: 16 organizations run these 47 centres. |
| `city_town` | text | Community the centre sits in. |
| `street_address` | text | Civic address, verbatim from the source. |
| `postal_code` | text | Full postal code, uppercased and trimmed. |
| `fsa` | text | First three characters of `postal_code`, uppercased. Blank if the postal code is blank. |
| `latitude` | double | **The corrected latitude**, taken from the source column named `x_coordinate`. Range 43.53 to 46.69. Give this column Tableau's Latitude geographic role. |
| `longitude` | double | **The corrected longitude**, taken from the source column named `y_coordinate`. Range -66.12 to -59.97. Give this column Tableau's Longitude geographic role. |
| `phone` | text | Public phone number. |
| `email` | text | Public email address, blank when not published. |
| `web` | text | Provider website, blank when not published. |
| `facebook` | text | Provider Facebook page, blank when not published. |
| `twitter` | text | Provider Twitter account, blank when not published. |
| `has_email` | integer | 1 when `email` is non-blank, else 0. |
| `has_web` | integer | 1 when `web` is non-blank, else 0. |
| `has_facebook` | integer | 1 when `facebook` is non-blank, else 0. |
| `has_twitter` | integer | 1 when `twitter` is non-blank, else 0. |
| `contact_channels` | integer | The four flags summed, 0 to 4. |
| `region_centres` | integer | Total centres in this row's region. Repeats on every row of that region. |
| `region_share_pct` | decimal(6,2) | That region's share of all 47 centres. Repeats on every row of that region, which makes it the cross-check for the Tableau FIXED expression. |

## `dashboard/data.js`

Generated by `run.py` from `out/mart_services.csv`. It is a single `const DATA = [...]` array holding the same 47 rows with the same column names, one object per centre. It exists so the dashboard opens under `file://` with no server and no fetch. It carries no computed figures: the dashboard derives every number it shows from these rows.
