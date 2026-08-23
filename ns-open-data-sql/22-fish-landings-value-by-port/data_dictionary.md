# Data dictionary

All dollar figures are Canadian dollars (CAD), carried as `DECIMAL(18,2)` in SQL and written to CSV with two decimal places. All weights are kilograms, carried the same way. Percentages are rounded to two decimals and price per kg to four, in both cases after the exact decimal division. Blank means the figure does not apply to that row or was suppressed at source; blank never means zero.

## out/fish_landings.csv (also expected/fish_landings.csv)

One sectioned result file, 212 rows. Columns not meaningful for a section are blank.

| Column | Type | Meaning |
| --- | --- | --- |
| section | text | Which block the row belongs to: `summary`, `row_classes`, `totals_tie`, `top_ports`, `by_county`, `by_year`, or `county_coverage`. |
| rank | integer | Position within the section. Ranking sections order by dollars descending; `by_year` orders by year and `county_coverage` by county then year. |
| measure | text | Label for `summary`, `row_classes`, and `totals_tie` rows (for example `grand_total`, `port_rows_kgs_only`, `sum_by_county`). Blank elsewhere. |
| year | text | Calendar year, 2017 through 2024. Filled for `by_year` and `county_coverage` rows. |
| county | text | Nova Scotia county. Filled for `by_county`, `county_coverage`, and the port rows in `summary` and `top_ports`. |
| port | text | Port display label, carrying the county in brackets only where a port name repeats across counties (for example `Other (Yarmouth)`). Filled for `top_ports` and the `top_port` summary row. |
| records | integer | How many source rows the figure covers. In `row_classes` it is the count of rows in that class. |
| kgs | kilograms, 2 dp | Kilograms landed, summed only over rows that report kilograms. |
| dollars | CAD, 2 dp | Purchase value, summed only over rows that report dollars. In `county_coverage` it is the bottom-up sum of that county's port rows for that year. |
| published_dollars | CAD, 2 dp | The province's own `Total for <County> County` figure. Filled in `county_coverage`, in the `published_county_dollars` summary row, and in the `excluded_county_total_rows` class row. Blank everywhere else. |
| price_per_kg | CAD per kg, 4 dp | Dollars over kilograms, computed only from rows where both measures are present and only where those kilograms exceed `min_kgs_for_price`. At county and year level this is a weighted average across every species landed, not a price for any one species. |
| share_pct | percent, 2 dp | The row's share of total dollars. 100.00 on the grand-total row. |
| cumulative_share_pct | percent, 2 dp | Running share of total dollars down the ranking, filled only in `top_ports`. |
| delta | CAD, 2 dp | In `by_year`, the change in dollars against the previous year (blank in 2017). In `county_coverage` and on the `published_county_dollars` summary row, the bottom-up sum minus the published figure, so a negative value is landed value the province reports at county level but suppresses at port level. |
| delta_pct | percent, 2 dp | The same comparison as `delta`, expressed against the earlier or published figure. |

### Section notes

- **`row_classes`** accounts for all 2,300 snapshot rows. Ranks 1 to 7 partition them: 144 excluded county aggregate rows plus 2,156 port rows, and those 2,156 split into 693 `both_present`, 0 `kgs_only`, 0 `dollars_only`, and 1,463 `both_blank`. Rank 8, `port_rows_wharf_qualifier_merged`, is an overlay on those rows rather than a class of its own, counting the 16 port rows that arrived carrying a wharf qualifier.
- **`totals_tie`** re-sums the port, county, and year breakdowns. All three rows must equal the grand total in dollars and in kilograms independently, because the two measures are suppressed independently.

## bi/exports/mart_fish_landings.csv (copy of out/mart_fish_landings.csv)

One row per analysed port record, 2,156 rows. `dollars` sums to exactly $8,716,996,237.83 and `kgs` to 1,265,656,315.49, the same totals the sectioned file proves. The 144 excluded county aggregate rows are deliberately not here; including them would let a report double count the province.

| Column | Type | Meaning |
| --- | --- | --- |
| year | integer | Calendar year, 2017 through 2024. Use this for year arithmetic in DAX and Tableau; the mart has no date column. |
| county | text | Nova Scotia county. Give this the County geographic role for Canada in Tableau. |
| port | text | Port name after the wharf qualifier is rolled in. Not unique on its own: `Other` appears in 18 counties, `Little Harbour` in 6, `Little River` in 2. |
| port_label | text | Display label, unique across all 271 ports, carrying the county in brackets only where the port name repeats. Group on this in a BI tool. |
| is_named_port | integer 0/1 | 1 for a real named port, 0 for the province's residual `Other` bucket for that county and year. |
| kgs | kilograms, 2 dp | Kilograms landed on this record. Blank when suppressed at source, never zero. |
| dollars | CAD, 2 dp | Purchase value on this record. Blank when suppressed at source, never zero. |
| measure_class | text | Which measures this record reports: `both_present`, `kgs_only`, `dollars_only`, or `both_blank`. Filter to `both_present` before computing price per kg. |
