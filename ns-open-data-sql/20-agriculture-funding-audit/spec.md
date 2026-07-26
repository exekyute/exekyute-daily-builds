# Spec: agriculture funding payments audit

## Purpose

Turn the province's agriculture funding payment list into an audit-style result: who receives the most money, how concentrated the dollars are, which payments look like possible duplicates, and how each division's spending moved year over year. Every figure is deterministic and re-derivable from the committed snapshot.

## Inputs

One file: `data/raw/ns_agriculture-funding_2026-07-06.csv`, a pinned snapshot of Socrata dataset `jv92-pedy` (see SOURCE.md). Columns: department, division, program_name, client_name, payment_amount, fiscal_year. All 6,324 rows belong to the Department of Agriculture.

## Cleaning rules (02_transform.sql)

1. **Amounts.** `payment_amount` is cast to `DECIMAL(18,2)`. A value that will not cast fails the run instead of silently becoming NULL. The snapshot has no blank, non-numeric, or negative amounts.
2. **Division.** `Programs & Business Risk Management` (the 2014-2015 through 2017-2018 spelling) is canonicalized to `Programs and Business Risk Management` (the 2018-2019 through 2020-2021 spelling); they are the same unit written two ways. `Programs` (2021-2022 onward) stays its own label because merging it with the older unit would be an interpretive judgment, not a spelling fix.
3. **Program names.** Trimmed, runs of spaces collapsed. Blank or missing program names (21 rows, all 2017-2018 exhibition and fair grants worth $196,208.74) become the literal label `(program not stated)` so they group and export like any other program. Program-name wording variants (for example `Vet Student Placement` vs `Veterinary Student Placement`) are left as distinct programs.
4. **Recipient names.** Trimmed, runs of spaces collapsed, then grouped on the lowercased result (`recipient_key`). That folds 13 pure case or spacing variant pairs (for example `TapRoot Farms Inc` and `Taproot Farms Inc`). The display spelling per key is the most frequent raw spelling, ties broken alphabetically. Variants beyond case and spacing, such as `Horticulture NS` vs `Horticulture Nova Scotia`, are left as distinct recipients: collapsing them would need fuzzy matching, which is not deterministic.
5. **Fiscal year.** `fy_start` is the integer first year of the label (`2014-2015` gives 2014), used for ordering and for the year-index pattern in the BI mart.

## Duplicate-payment candidate rule (word for word)

Rows sharing the same recipient_key, program_name, amount, and fiscal_year, appearing more than once, are duplicate-payment candidates. They are candidates, not confirmed duplicates: a program can legitimately pay the same recipient the same amount twice in one fiscal year (for example two identical claims under one program), and confirming a true duplicate needs payment-level detail this dataset does not carry.

The snapshot yields 9 candidate groups covering 23 payments; the 14 occurrences beyond the first in each group are worth $308,000.00.

## Analysis steps (03_analysis.sql)

1. `grand_total`: payment count and dollar sum over the cleaned table. Every later breakdown must re-sum to this number exactly.
2. `recipient_totals`: dollars and payment count per recipient_key, ranked by dollars, ties broken by key.
3. `program_totals`: the same per program label.
4. `division_year_totals`: dollars per division per fiscal year, with year-over-year change and percent computed by `LAG` over each division's own observed year sequence.
5. `duplicate_candidates`: the groups matching the rule above, ranked by amount then recipient, each carrying its occurrence count and the extra dollars beyond the first occurrence.
6. `funding_audit`: the six sections stacked into one table with a fixed sort key:
   - `summary`: grand total, top-10 recipient dollars with their share, duplicate-candidate extra dollars with their share.
   - `totals_tie`: the recipient, program, and division-year breakdowns re-summed; all three rows must equal the grand total to the cent.
   - `top_recipients`: top 25 recipients with share and cumulative share.
   - `program_shares`: all 106 program labels with share.
   - `yoy_division`: division dollars per year with YoY change.
   - `duplicate_candidates`: the flagged groups.
7. `mart_funding_audit`: one cleaned row per source payment (6,324 rows) with the duplicate flag attached, exported for the Power BI face. Its dollar sum equals the grand total.

## Outputs

- `out/funding_audit.csv`: the sectioned audit result, diffed against `expected/funding_audit.csv`.
- `out/mart_funding_audit.csv`, copied to `bi/exports/mart_funding_audit.csv`: the payment-level BI mart.

## Edge cases

- **Blank program names** are the only blanks in the snapshot; they get the `(program not stated)` label (rule 3). Without that rule the equality join to the duplicate groups would silently drop those 21 rows, because NULL never equals NULL.
- **Recipient variants** beyond case and spacing stay distinct, so `Dalhousie University` and `Dalhousie Agricultural Campus` rank separately even though they are related institutions.
- **Division gaps**: `Value Chain Development` exists only in 2014-2015, so it never gets a YoY row; the first year of every division shows blank YoY fields.
- **Ties in rankings** break on the recipient key or program name, alphabetically, so rank order never depends on scan order.

## Determinism and the money tie

Dollar math runs in `DECIMAL(18,2)` end to end; percentages are display values rounded to two decimals after the exact division. Every exported query ends in an explicit `ORDER BY`, so the files are byte-stable run to run. The `totals_tie` section makes the cent-level tie visible inside the golden file itself: three independent re-summations of the same $75,357,902.03.
