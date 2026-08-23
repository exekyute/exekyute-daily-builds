# Data dictionary

Two files are defined here: the sectioned result the golden diff checks, and the property-level mart Tableau reads. Both are UTF-8.

Throughout, **units** means dwelling units and **properties** means source rows, one per listed property record. A families row is one civic address; a seniors row is one named building. The two counts are never mixed, because a row means a different thing in each source.

## out/housing_supply.csv (also expected/housing_supply.csv)

One sectioned result file, 90 rows plus a header. Columns that carry no meaning for a section are blank.

| Column | Type | Meaning |
| --- | --- | --- |
| section | text | Which block the row belongs to: `summary`, `exclusions`, `reconciliation`, `program_totals`, `county_totals`, or `county_program`. |
| rank | integer | Position within the section, unique inside it. The three measure sections number their rows in reading order; `program_totals` and `county_totals` rank by units descending with the name breaking ties; `county_program` runs county rank then program order. |
| measure | text | Label for a `summary`, `exclusions`, or `reconciliation` row, for example `provincial_units` or `units_grid_minus_combined`. Blank in the three tabular sections. |
| county | text | Canonical county name. Filled in `county_totals` and `county_program`, and on the one summary row that names a county (`top_county_units`). |
| program_type | text | `Families` or `Seniors`. Filled in `program_totals` and `county_program`. |
| properties | integer | Property records for the row. Filled in the three tabular sections only. |
| units | integer | Dwelling units for the row. Filled in the three tabular sections only. |
| share_pct | percent, 2 dp | The row's share of the 11,251 provincial units. 100.00 on the `provincial_units` summary row. Rounded for display, so a column of shares can miss 100.00 by a few hundredths. |
| value | integer | The scalar for a `summary`, `exclusions`, or `reconciliation` row. Blank in the three tabular sections. Every measure in those sections is a whole count, whether of units, property records, source rows, counties, grid cells, or substitutions. |

### The `summary` measures

| measure | Meaning |
| --- | --- |
| provincial_units | Total dwelling units across both sources. 11,251. |
| provincial_properties | Total property records across both sources. 3,289. |
| counties_in_universe | Distinct normalized counties present in either source. 18. |
| program_types | Rows in the `const_program_type` constant. 2. |
| grid_cells | Cells in the county-by-program cross join. 36. |
| grid_cells_with_zero_units | Cells holding no units. 0, so every county carries both programs. |
| counties_without_family_units | Counties whose Families cell is zero. 0. |
| counties_without_senior_units | Counties whose Seniors cell is zero. 0. |
| county_name_substitutions | Rows whose county was rewritten by `const_county_map`. 0. |
| authority_name_substitutions | Rows whose housing authority was rewritten by `const_authority_map`. 1. |
| top_county_units | Units in the highest-ranked county, with that county in the `county` column and its share in `share_pct`. Halifax, 3,763, 33.45 percent. |

### The `exclusions` measures

Row accounting, reported at its count whether or not anything was excluded.

| measure | Meaning |
| --- | --- |
| rows_read_families | Rows loaded from the families snapshot. 2,947. |
| rows_read_seniors | Rows loaded from the seniors snapshot. 342. |
| rows_read_total | The two added. 3,289. |
| excluded_county_blank | Rows whose county is empty after normalization. 0. |
| excluded_units_not_a_number | Rows whose unit value will not cast to an integer. 0. |
| excluded_units_not_positive | Rows whose unit value casts but is below 1. 0. |
| excluded_total | All excluded rows. 0. |
| rows_kept_total | Rows carried into the analysis. 3,289. |
| row_accounting_difference | Rows read minus excluded minus kept. Must be 0. |

### The `reconciliation` measures

Two independent paths to the same totals. Every `_minus_` row must read 0.

| measure | Meaning |
| --- | --- |
| units_families | Units from the families source. 3,479. |
| units_seniors | Units from the seniors source. 7,772. |
| units_sum_of_sources | The two added. 11,251. |
| units_combined_total | Units over the stacked table. 11,251. |
| units_sources_minus_combined | Difference between the two lines above. 0. |
| units_sum_of_county_grid | Units re-summed across all 36 grid cells. 11,251. |
| units_grid_minus_combined | Difference between the grid and the combined total. 0. |
| properties_families | Property records from the families source. 2,947. |
| properties_seniors | Property records from the seniors source. 342. |
| properties_sum_of_sources | The two added. 3,289. |
| properties_combined_total | Property records over the stacked table. 3,289. |
| properties_sources_minus_combined | Difference between the two lines above. 0. |
| properties_sum_of_county_grid | Property records re-summed across all 36 grid cells. 3,289. |
| properties_grid_minus_combined | Difference between the grid and the combined total. 0. |

### The tabular sections

| section | Rows | Contents |
| --- | --- | --- |
| program_totals | 2 | Units and property records per program type, with each program's share of provincial units. |
| county_totals | 18 | Units and property records per county across both programs, with each county's share of provincial units. |
| county_program | 36 | One row per county-by-program cell, with the cell's share of provincial units. Ordered by county rank, then Families before Seniors. |

## bi/exports/mart_housing.csv (copy of out/mart_housing.csv)

One row per kept property record. 3,289 rows; `units` sums to exactly 11,251, the same provincial total the result proves.

| Column | Type | Meaning |
| --- | --- | --- |
| program_type | text | `Families` or `Seniors`, the source the row came from. |
| source_id | text | The source row identifier: `uid` in the families file, `id` in the seniors file. The two files number independently, so the key is program_type plus source_id, not source_id alone. Keep it as text in Tableau or it will be read as a measure. |
| county | text | Canonical county name, after the mechanical rule and `const_county_map`. Eighteen values. |
| municipality | text | Municipal unit as published, for example `Municipality of the County of Inverness`. Finer than county and not a strict nesting of it in every case, so county is the level the result groups on. |
| community | text | Community name: `community` in the families file, `city` in the seniors file. |
| property_label | text | `civic_address` for a families row, `name` for a seniors row. A street address and a building name, in one column, which is why the column is not called address. |
| housing_authority | text | Regional housing authority, after `const_authority_map`. Five values. Authorities cross county lines, so this is not a county proxy. |
| units | integer | Dwelling units on the property record. Sums to 11,251. |
| latitude | decimal | Latitude in decimal degrees, from the source `y_coordina` column. Range 43.45 to 46.89. |
| longitude | decimal | Longitude in decimal degrees, from the source `x_coordina` column. Range -66.32 to -59.85. Negative, being west of the prime meridian. |

Both coordinate columns are populated on every row. Note the source naming: `x_coordina` holds longitude and `y_coordina` holds latitude, the reverse of what the names suggest, and the transform reads them that way.
