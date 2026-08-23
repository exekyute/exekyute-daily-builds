# Spec: Invest NS deal book

## Purpose

Turn the province's record of Invest Nova Scotia financial programs into a deal book: how much money went to which sectors, which counties, which deal types, and which years, plus who received the most. Every figure is deterministic and re-derivable from the committed snapshot, and every dollar breakdown ties back to the same grand total to the cent.

## Inputs

One file: `data/raw/ns_invest-ns-financial-programs_2026-07-25.csv`, a pinned snapshot of Socrata dataset `6aac-8xtn` (see SOURCE.md). 4,553 rows covering fiscal years 2018-2019 through 2023-2024. Columns used: `object_id_`, `account_name`, `nsbi_sector`, `deal_type`, `nsbi_financial_contribution`, `place_name`, `nsbi_county`, `postalcode`, `fiscal_year`, `longitude`, `latitude`. The `geolocation` column is loaded but not used: it repeats the latitude and longitude pair as a well-known-text point.

## The blank-contribution rule

**A blank `nsbi_financial_contribution` is counted, reported on its own row, and left out of every sum and every share-of-total denominator. It is never read as zero.**

In SQL the rule is one expression: `NULLIF(tidy(x), '')` turns a blank into NULL, `sum()` skips NULL, and so does the denominator that every `share_pct` divides by. The count lands in the `blank_contribution_deals` row of the summary section.

A real zero is kept as a real zero. Zeros carry into the counts, add nothing to the money, and get their own summary row: this snapshot has **257** of them, most from 2018-2019 trade missions and trade shows, which the province records as deals with no dollar figure attached.

The cast itself is deliberately strict. A value that is neither blank nor numeric fails `CAST(... AS DECIMAL(18,2))` and stops the run, rather than turning into a silent NULL that would look like a blank. This snapshot has none.

## Cleaning rules (02_transform.sql)

1. **`tidy()`** trims and collapses runs of spaces. **`label_key()`** lowercases the tidy form. Two labels that differ only in case or spacing therefore share a key and group together. The display spelling per key is the most frequent raw spelling, ties broken alphabetically, so the label never depends on scan order.
2. **Counties** get one extra step. The named constant `COUNTY_HALIFAX_VARIANTS` lists every keyed label meaning Halifax County: `halifax`, `halifax (urban)`, `halifax (rural)`, `halifax regional municipality`. All four fold onto `COUNTY_HALIFAX_CANONICAL`, which is `Halifax`. Nova Scotia has one Halifax county and the urban, rural, and regional-municipality qualifiers describe the same boundary, so this is a lookup onto the province's fixed 18-county vocabulary rather than a judgment call. After the fold the county column holds exactly those 18 counties plus two labels that are not counties.
3. **Non-county labels.** `COUNTY_NON_GEOGRAPHIC_LABELS` names the two values in the county column that do not name a county: `Not Applicable / Unknown` and `province-wide`. They keep their rows, keep their dollars, and carry a flag so the geographic views can report them instead of dropping them.
4. **Sectors and deal types** get case and spacing folding only. Abbreviation and longhand pairs such as `BDP` and `Business Development Program` stay distinct. Expanding one into the other needs a program crosswalk that neither the dataset nor the portal publishes, so the pipeline would be guessing rather than cleaning. See "Reading the labels" below, because this choice shapes how the sector and deal-type tables should be read.
5. **Money** is cast to `DECIMAL(18,2)` after the blank rule above.
6. **Fiscal year.** `fy_start` is the integer first year of the label, so `2018-2019` gives 2018. It orders the year sections and gives Tableau a numeric year to filter on.
7. **Coordinates** are cast from the `latitude` and `longitude` columns. A blank pair leaves `is_mappable` false, counted, never guessed at. A pair that falls outside the named constant `NS_BOUNDS` (latitude 43.0 to 47.5, longitude -67.0 to -59.0) leaves `in_ns_bounds` false. The rectangle is drawn wide on purpose: it is there to catch a point that is plainly somewhere else, not to trim points near the coastline.

## Reading the labels

The sector and deal-type columns are not written the same way from year to year, and the pipeline reports them as filed. That choice changes how the ranked tables should be read, so it is worth spelling out.

- **Deal types.** The naming convention moves with the fiscal year. `Export Growth Program` appears in 2018-2019 and `EGP` from 2019-2020. `Business Development Program` in 2018-2019, `BDP` in 2020-2021. `Innovation Rebate Program` in 2018-2019, `IRP` afterwards. `Payroll Rebate` and `PRB` alternate across the six years. The `deal_type_mix` section makes the switch visible year by year. Read together, the payroll rebate labels (`PRB` plus `Payroll Rebate`) account for $146,996,142.00, or 50.81 percent of all dollars, and the innovation rebate labels (`IRP`, `Innovation Rebate Program`, `SME IRP`) for $92,803,055.00, or 32.08 percent.
- **Sectors.** `ICT` and `ICT (includes Digital Media)` are ranked separately and together hold $114,546,810.44, or 39.60 percent. `Clean Tech`, `CleanTech`, and `Clean Technology` are three labels. `Finacial Services` is a typo of `Financial Services` and stays its own row. Folding any of these would require deciding which spelling is canonical without a published list to decide against.

Both figures above are arithmetic on the golden file rather than a merge inside the pipeline. Anyone re-reading that file sees the same fragmentation and can combine the labels on their own terms.

## Analysis steps (03_analysis.sql)

1. `grand_total`: deal count and dollar sum over the cleaned table. Every later breakdown must re-sum to this number exactly.
2. `contribution_classes`: blank, zero, negative, and positive deal counts. They add back to the row count, so nothing leaves the file unreported.
3. `geography_classes`: deals with a non-county label, deals with no coordinate pair, and deals with coordinates outside Nova Scotia, each with its dollars.
4. `sector_totals`, `county_totals`, `deal_type_totals`: dollars and deal counts per label, ranked by dollars, ties broken on the label itself.
5. `fiscal_year_totals`: dollars per year in year order, with the change against the previous year from `LAG`. The first year has no prior, so its change columns stay blank rather than reading as zero.
6. `recipient_totals`: dollars per account, ranked, tie broken on the account name.
7. `deal_type_mix`: dollars per deal type per fiscal year, with each type's share of its own year.
8. `deal_book`: the eight sections stacked into one table with a fixed sort key.
   - `summary`: grand total, every counted class, and the leading sector, county, deal type, and recipient.
   - `totals_tie`: the sector, county, deal-type, fiscal-year, and recipient breakdowns re-summed. All five rows must equal the grand total to the cent.
   - `by_sector`: all 39 sector labels with share of total.
   - `by_county`: all 20 county labels with share of total, the two non-county ones marked.
   - `by_deal_type`: all 28 deal-type labels with share of total.
   - `by_fiscal_year`: the six years with year-over-year change in dollars and percent.
   - `top_recipients`: the top 25 accounts (named constant `TOP_RECIPIENTS_N`).
   - `deal_type_mix`: 41 rows of deal type by year.
9. `mart_deal_book`: one cleaned row per source deal (4,553 rows) with coordinates and flags, exported for the Tableau face. Its contribution column sums to the grand total.
10. `dash_deal_book`: the same money aggregated to the grain the browser page needs, fiscal year by sector by county by deal type (1,007 rows). Its contribution column also sums to the grand total.

## The dashboard, and the numbers it has to match

`dashboard/dashboard.html` opens by double-clicking. It has no framework, no CDN, no fetch, and no file picker. `run.py` writes `dashboard/data.js` as a `const DATA = [...]` literal holding the 1,007 cube rows; that file is plumbing and carries no logic. Every figure on the page is added up in JavaScript from `DATA`, in whole cents, so nothing is hardcoded and nothing drifts.

The derived figures must equal these golden values exactly:

| Figure | Value |
| --- | --- |
| Total contribution | $289,279,591.01 |
| Deals recorded | 4,553 |
| Leading sector | ICT (includes Digital Media), $89,152,964.26, 30.82% |
| Leading county | Halifax, $208,658,110.23, 72.13% |
| Leading deal type | PRB, $82,531,894.00, 28.53% |
| 2018-2019 | $32,480,991.00 |
| 2019-2020 | $48,411,392.00 |
| 2020-2021 | $25,148,821.00 |
| 2021-2022 | $72,302,139.00 |
| 2022-2023 | $51,464,335.26 |
| 2023-2024 | $59,471,912.75 |

Beyond the headline, the page's sector, county, and deal-type ladders reproduce all 39, 20, and 28 rows of the matching golden sections, with the same order, dollars, deal counts, and two-decimal shares.

## Outputs

- `out/deal_book.csv`: the sectioned deal book, diffed against `expected/deal_book.csv`.
- `out/mart_deal_book.csv`, copied to `bi/exports/mart_deal_book.csv`: the deal-level Tableau mart.
- `out/dash_deal_book.csv`, re-emitted as `dashboard/data.js`: the dashboard cube.

## Edge cases

- **Zero dollars, real deals.** 257 deals record a contribution of exactly zero. They are counted everywhere and add nothing to any sum. Six deal-type labels total zero dollars across the whole file: `PMA`, `Project Management`, `Scale-Up Hub Program`, `Trade Mission (Incoming)`, `Trade Mission (Outgoing)`, and `Trade Show`. They still appear in the ranked table, at the bottom, with their deal counts intact.
- **One deal with no coordinates.** Object 3495, Sea Crest Fisheries Ltd. in Saulnierville, has blank `latitude` and `longitude` while its `geolocation` column carries the point. The pipeline reads the two coordinate columns only, so that row is counted as not mappable rather than back-filled. Parsing a well-known-text point as a fallback would add a second coordinate rule that applies to exactly one row in the file.
- **Seven deals outside Nova Scotia.** Coordinates place them in Toronto, Calgary, Dublin, and three at latitude 0, longitude 0. They are worth $2,465,355.12 and stay in every dollar total; only the point map leaves them out, and it says so.
- **Two non-county labels.** `province-wide` carries one deal worth $2,016,000.00; `Not Applicable / Unknown` carries one worth nothing. Both keep their money in the totals and are marked in the county section.
- **Mojibake in account names.** Twelve rows carry account names that were mis-encoded before publication, for example `IBM Canada Limited/IBM Canada LimitÃ©e` and two spellings of `Mind's Eye Creative Consulting` broken two different ways. They are exported exactly as filed. Repairing them means guessing which characters were lost, and the two broken spellings of the same firm would still not merge without fuzzy matching.
- **Ties in rankings** break on the label or account name, alphabetically, so rank order never depends on scan order.

## Determinism and the money tie

Dollar math runs in `DECIMAL(18,2)` end to end. Percentages are display values rounded to two decimals after the exact division. Every exported query ends in a total `ORDER BY` whose last term is unique, `nsbi_sector`, `nsbi_county`, `deal_type`, `account_name`, or `object_id`, so a sort never rests on a measure alone and the files are byte-stable run to run.

The `totals_tie` section makes the cent-level tie visible inside the golden file itself: five independent re-summations of the same $289,279,591.01, by sector, by county, by deal type, by fiscal year, and by recipient. The dashboard runs a sixth re-summation in the browser, in whole cents, and lands on the same figure.
