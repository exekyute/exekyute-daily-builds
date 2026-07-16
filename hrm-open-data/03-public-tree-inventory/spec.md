# Spec: public tree inventory and species diversity

## Purpose

Describe Halifax Regional Municipality's public-tree inventory: what is on it by
species, size class, and setting, and how diverse the canopy is. One SQL pipeline
produces the golden result tables (a species ranking, two class distributions, and a
summary), one wide per-tree mart for the two BI tools, and the embedded aggregates
behind the browser dashboard. Every figure ties back to the same 78,896-tree total.

## Inputs

- `data/raw/hrm_public-trees_2026-07-09.csv`: pinned snapshot of the Public Trees layer
  (`HRM::public-trees`), pulled 2026-07-09 with WGS84 coordinates and a stable
  `OBJECTID` order so a re-pull pages deterministically. 78,896 rows, one per tree.
  Columns and the exact pull query are in SOURCE.md.

## Cleaning and normalization (02_transform)

No rows are dropped. `TREEID` is unique and every row is a real asset, so unusable
attribute values are labelled rather than filtered; the mart total stays equal to the
raw row count. Per column:

1. `tree_id`: `TREEID`, trimmed.
2. `species_common`: `SP_COMM`, trimmed with internal whitespace collapsed. The source
   already ships title case, so no case change is applied. Blank names and the literal
   `Unknown Species` are folded into a single `Unidentified` bucket.
3. `species_scientific`: `SP_SCIEN`, trimmed and normalized to binomial case (first
   letter upper, the rest lower) to reconcile inconsistent source casing. Blank and
   `Unknown Species` become `Unknown`.
4. `dbh`: `DBH` cast to an integer (the size-class code 1 to 9), or null.
5. `dbh_class`: the code bucketed into ordered tiers `Class 1-2`, `Class 3-4`,
   `Class 5-6`, `Class 7-9`, and `Unknown` for a null code.
6. `setting`: `LOCGEN` mapped `ROW` to `Street right-of-way`, `OSP` to `Open space`,
   anything else to `Unknown`.
7. `wires`: `WIRES` mapped `Y` to `Under wires`, `N` to `Clear of wires`, blank or
   anything else to `Unknown`.
8. `install_year`: `INSTYR` kept only when it casts to an integer in 1900 to 2026;
   otherwise null. This drops the 0, blank, and out-of-range values (one is 2105).
9. `owner`: `HRM` when the source says so, else `Unknown`.
10. `status`: `INS` mapped to `Installed`, else `Unknown` (uniformly `Installed` here).
11. `lat`, `lon`: cast to numeric and rounded to 6 decimal places (about 0.1 m),
    which keeps the mart compact and byte-stable.

## Analysis, step by step (03_analysis)

1. `species_ranking`: identified species only (the `Unidentified` bucket is not a
   species). Each species carries its representative scientific name, chosen as the most
   frequent scientific name recorded under that common name, ties broken alphabetically
   so the pick is deterministic. `tree_count` is the count; `share_of_all_pct` is that
   count over ALL 78,896 trees, so the ranking's counts plus the unidentified count
   equal the inventory. `species_rank` is `RANK()` by count descending, name ascending.
2. `dbh_class_distribution`: count and share of all trees by DBH tier, with a fixed
   `class_order` for a stable sort.
3. `wires_distribution`: count and share of all trees by wires-present category. This is
   the categorical that stands in for the condition rating the dataset does not carry.
4. `setting_distribution`: count and share of all trees by general location.
5. `summary`: one row per headline metric (total trees, identified, unidentified,
   distinct species, top species and its count and share, most common DBH class, trees
   with a recorded planting year, and the earliest and latest recorded year). Every
   value is read from the tables above.
6. `headline`: three ready-to-print lines built from `summary`; `run.py` prints them and
   computes nothing.

## Outputs (99_export)

Every export query ends in ORDER BY.

- `out/species_ranking.csv` (golden, ordered by rank then name).
- `out/dbh_class_distribution.csv` (golden, ordered by class code).
- `out/wires_distribution.csv` (golden, ordered by count descending then label).
- `out/setting_distribution.csv` (golden, ordered by count descending then label).
- `out/summary.csv` (golden, ordered by metric ordinal).
- `out/mart_trees.csv`: one wide row per tree, ordered by `tree_id`. `run.py` copies it
  to `bi/exports/mart_trees.csv` for Tableau and Power BI.

`run.py verify` diffs each file in `expected/` against `out/` row for row and prints
PASS on an exact match. The five golden files above are the verified surface. The mart
is deterministic by the same rules (fixed ORDER BY, rounded coordinates) and is frozen
in `bi/exports/`.

## Dashboard re-derivation

`run.py` re-emits the five aggregates as `dashboard/data.js` (a `DATA` object, not the
78,896 raw rows). `dashboard/index.html` renders from `DATA` and re-derives its headline
in the browser:

- Total trees = sum of the species-ranking counts plus the unidentified count. Must
  equal `summary.total_trees` = **78,896**.
- Distinct species = the number of species rows. Must equal `summary.distinct_species`
  = **250**.

The page prints both derived figures and states whether they match the golden summary.
Because the page sums the same exported counts the golden was built from, the two sides
cannot drift.

## Headline figures

- **78,896** public trees across **250** distinct identified species; **4,763** trees
  are not yet identified.
- Most common species: **Norway Maple** (Acer platanoides), **10,276** trees, **13.02%**
  of the inventory.
- Size classes: `Class 1-2` holds 41,855 trees (53.05%), the largest tier; `Class 7-9`
  holds 2,003 (2.54%).
- Setting: 73,045 trees (92.58%) stand in the street right-of-way, 5,851 (7.42%) in
  open space.
- **9,997** trees carry a recorded planting year, spanning **2013 to 2025**.

## Determinism

The snapshot is pinned and committed; the pipeline reads only that file. Every exported
query ends in ORDER BY, coordinates are rounded to fixed precision, shares are cast to a
fixed 2-decimal type, and `run.py` holds no analytical logic beyond execute, copy,
re-emit, and diff. Any age or date arithmetic uses the 1900 to 2026 literal window, not
`CURRENT_DATE`. Re-running `python run.py` on any machine reproduces every golden file
byte for byte.

## Edge cases

- Unidentified trees: blank common name and the literal `Unknown Species` are one
  `Unidentified` bucket, excluded from the species count but kept in the total.
- Null DBH code: 575 trees, placed in the `Unknown` size class.
- Blank wires flag: 648 trees, placed in the `Unknown` wires category.
- Sparse planting year: install year is null for 68,899 trees; the planting-year trend
  in Power BI covers only the 9,997 with a recorded year.
- One common name can map to more than one scientific name in the source (a few
  mislabelled rows); the ranking shows the modal scientific name per common name.
