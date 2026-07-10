# Spec: liquor-license density by community

## Purpose

Measure how permanent liquor licenses concentrate across Nova Scotia communities,
and describe the license-type mix inside each community. The headline is the
community holding the most licenses and its dominant type.

## Inputs

- **Dataset:** Permanent Liquor Licenses (`en23-iwca`), pinned snapshot at
  `data/raw/ns_liquor-licenses_2026-07-05.csv`, 2474 rows. Details in SOURCE.md.
- **Columns used:**
  - `city_town`: the community key. One license belongs to one community.
  - `license_type`: the category of license (for example Eating Establishment,
    Lounge, Club, Special Premises).
  - `license_number`: carried through as the row identity; not aggregated.
- Columns present but unused: `establishment`, `street_address`, `province`,
  `postal_code`, `location`.
- **How community is keyed:** on the cleaned `city_town` value alone. Province is
  not part of the key, because every establishment in the set sits in Nova Scotia
  and the province column carries a few stray non-NS entries that add no signal.

## Cleaning and validation rules

Applied in `sql/02_transform.sql`:

1. **Community.** Trim `city_town`. If it is null or empty after trimming, set the
   community to `(Unknown)` so the license is still counted rather than dropped.
   In this snapshot exactly one row (license 007061) lands in `(Unknown)`.
2. **License type.** Trim `license_type` and collapse any internal run of
   whitespace to a single space. This folds the source value
   `Permanent  Special Occasion` (two spaces) into `Permanent Special Occasion`,
   so a type is not split into two by a stray space.
3. No rows are filtered out. The cleaned table holds the same 2474 rows as the
   snapshot, so the per-type counts sum back to 2474.

## Analysis logic, step by step

Applied in `sql/03_analysis.sql`:

1. **Count per type per community** (`per_type`): group the cleaned rows by
   community and license type, count the rows in each group.
2. **Total per community** (`per_community`): sum the per-type counts within each
   community to get its total licenses.
3. **Rank communities** (`ranked_community`): `dense_rank()` over community total,
   descending, so the busiest community is rank 1. Communities with equal totals
   share a rank.
4. **Assemble the mart:** join per-type counts to their community total and rank,
   then for each row compute:
   - `type_share_pct`: the type's count divided by the community total, times 100,
     rounded to one decimal place.
   - `is_dominant_type`: 1 for the community's single most common type, else 0.
     The winner is chosen by highest `type_count`, with ties broken by
     `license_type` name ascending, so exactly one type per community is flagged.

## Outputs

`sql/99_export.sql` writes the mart to `out/license_density.csv`, one row per
community and license type. Columns are defined in data_dictionary.md. The export
is sorted by community total descending, then community name, then type count
descending, then license type name. The committed golden copy is
`expected/license_density.csv` (706 data rows).

## Edge cases

- **Missing community.** A blank or null `city_town` becomes `(Unknown)` rather
  than being discarded (rule 1 above).
- **License-type variants.** Whitespace differences in the source (the double
  space in `Permanent  Special Occasion`) are normalized so counts are not split.
- **Stray province values.** A handful of rows carry a province other than `NS`
  (and 21 carry none). Because the community key is `city_town` only, these rows
  still count toward their town and do not need special handling.
- **The `location` field** contains multi-line, quoted, geocoded text. It is read
  as text and ignored by the analysis.

## Determinism

The snapshot is pinned, every result query ends in `ORDER BY`, and rounding is
fixed at one decimal place. `expected/license_density.csv` was built from a first
verified run; `python run.py` rebuilds `out/` and diffs it against that golden
copy row for row, printing PASS only on an exact match.
