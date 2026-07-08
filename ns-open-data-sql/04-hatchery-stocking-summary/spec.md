# Spec: hatchery stocking summary

## Purpose

Roll the raw Fish Hatchery Stocking Records up into one summary table. For every
county, waterbody, species, and year it says how many stocking events took place,
how many fish were released, and what size the fish were at release. From that one
table a reader can read off the top species, the most stocked waterbody, and how
the effort changed year over year.

## Inputs

- **Dataset:** Nova Scotia Open Data, Fish Hatchery Stocking Records (`8e4a-m6fw`).
- **Snapshot:** `data/raw/ns_hatchery-stocking_2026-07-05.csv`, 15,000 rows.
- **Columns used:**
  - `county`: county the waterbody sits in.
  - `name`: waterbody name (becomes `waterbody`).
  - `type`: waterbody class, one of Brook, Flowage, Lake, Pond, River.
  - `number_released`: fish released in the event.
  - `stocking_date`: ISO timestamp of the release; only the year is used.
  - `fish_length_cm`: measured length at release.
  - `fish_weight_g`: measured weight at release.
  - `stock`: species (becomes `species`).
- Other columns in the source (easting, northing, objectives, growth stage,
  mark, hatchery, stock strain) are carried into the raw staging table but are
  not part of the summary.

## Cleaning and validation rules

1. **Trim text.** County, waterbody, type, and species are trimmed. One species
   value in the source carries a trailing space (`"Atlantic Salmon "`); without
   the trim it would split into a separate group from `"Atlantic Salmon"`.
2. **Year from date.** `stocking_year` is the first four characters of
   `stocking_date`, cast to an integer. Every date in the snapshot parses, and
   the years run 1976 to 2025.
3. **Whole fish counts.** `number_released` is cast to a whole number. A few
   records report zero fish released; they are kept as valid events that add
   nothing to the fish totals. No negative counts appear.
4. **Size measured, not assumed.** `fish_length_cm` and `fish_weight_g` are kept
   as measured, but a value of zero or below is read as "not recorded" and set to
   NULL, so it does not pull the average size at release toward zero. In the
   snapshot 10 records have no length and 192 have no weight.

## Analysis logic, step by step

The SQL runs in file-number order.

- **00_schema.sql** creates the raw staging table (all text) and the typed fact
  table.
- **01_load.sql** loads the committed snapshot into the staging table as text.
- **02_transform.sql** applies the cleaning rules above and writes the typed fact
  table, one row per source record.
- **03_analysis.sql** groups the fact table by `county`, `waterbody`,
  `waterbody_type`, `species`, and `stocking_year`, and for each group computes:
  - `stocking_events = count(*)`, the number of stocking records (the effort
    measure);
  - `fish_released = sum(number_released)`;
  - `avg_length_cm = round(avg(fish_length_cm), 2)` over records with a measured
    length;
  - `avg_weight_g = round(avg(fish_weight_g), 2)` over records with a measured
    weight.
- **99_export.sql** copies the summary to `out/stocking_summary.csv` with a fixed
  column order.

**Grouping keys.** The five grouping columns together identify each summary row.
**Average size.** Averages ignore missing measurements; a group with no measured
size gets a blank average. **Effort trend.** Summing `stocking_events` (or
`fish_released`) by `stocking_year` gives the trend over time.

## Outputs

`out/stocking_summary.csv`, one row per county, waterbody, waterbody type,
species, and year, with the event count, fish released, and average size. The
golden copy is `expected/stocking_summary.csv`. Columns are defined in
`data_dictionary.md`.

## Edge cases

- **Zero fish released.** Kept as events; contribute 0 to `fish_released`.
- **Missing size.** Length or weight of zero becomes NULL and is excluded from
  the average. A group where nothing was measured shows a blank average.
- **Trailing whitespace in species.** Removed by the trim so counts are not split.
- **Same waterbody name in different counties or of different types.** Kept
  apart, because county and waterbody type are part of the grouping key.
- **Year gaps.** The record has no stockings for some years (for example 2017
  and 2018). Those years simply have no rows; nothing is invented to fill them.

## Determinism

The snapshot is pinned and committed. Every result query ends in `ORDER BY` on
the full grouping key, which is unique per row, so the row order is fixed. The
golden file was built from a first verified run; a second run reproduces it byte
for byte, and `python run.py` prints PASS.
