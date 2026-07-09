# Spec

## Purpose

Rank Nova Scotia's provincial highway segments by traffic volume, show how fast each one is changing, and flag the segments that carry enough traffic to warrant a capacity review. The output is one deterministic table, `out/corridor_ranking.csv`.

## Inputs

Dataset: Traffic Volumes - Provincial Highway System (`8524-ec3n`), pulled to `data/raw/ns_traffic-volumes_2026-07-05.csv`. See SOURCE.md.

Columns used:

- `section_id`: the segment key. Every count belongs to one section, so the segment is keyed on this value.
- `date`: the count date. Only the four-digit year is read from it.
- `aadt`: annual average daily traffic, the volume this project ranks.
- `highway`, `section`, `county`, `section_description`, `section_length`: descriptive attributes carried through for labelling.

A single section can hold several count rows in the same year: one per direction, or one per count station, plus station-only rows that carry no AADT. That shape drives the cleaning rules below.

## Cleaning and validation

- Rows without a numeric `aadt` (station-only rows, blanks) are dropped. Only rows where `aadt` casts to an integer take part.
- A segment's AADT for a year is the **maximum** reported AADT across all of that year's count rows for the section. This gives the single busiest reported daily volume on the segment that year. The maximum is used rather than a sum because the number of count rows per year is not stable (some years hold one directional count, others hold several stations), so a sum would swing with the count layout rather than with real traffic.
- Descriptive attributes (`highway`, `section`, `county`, `section_description`, `section_length`) are read from the segment's most recent count, with the count `description` as a tie-break so the pick is fixed when a segment has more than one count in its latest year.

## Analysis

1. **Yearly series (`02_transform.sql`).** Collapse the raw counts to one row per segment per year, holding the peak AADT (the cleaning rule above).

2. **Previous reading (`03_analysis.sql`).** For each yearly reading, `LAG(aadt)` and `LAG(yr)` over `PARTITION BY section_id ORDER BY yr` return the segment's previous count. This window function is what the growth figure rests on.

3. **Latest reading and growth.** Keep each segment's most recent year. Growth is the annualized change from the previous count to the latest one:

       yoy_growth_pct = (pow(current_aadt / prior_aadt, 1 / (current_year - prior_year)) - 1) * 100

   Annualizing matters because the province re-counts most segments on roughly a three-year cycle, so the gap between a segment's two most recent counts is often more than one year. Annualizing turns that gap into a per-year rate, and reduces to the plain year-over-year change when the counts are one year apart. The figure is rounded to two decimals. A segment with only one count has no previous reading, so its growth is blank.

4. **AADT ranking.** `rank()` over `ORDER BY current_aadt DESC` gives `aadt_rank`. Ties share a rank; the output row order breaks ties by `section_id` so the sequence is fixed.

5. **Growth ranking.** A second `rank()` over `ORDER BY yoy_growth_pct DESC` ranks the fastest-growing segments, but only among established corridors: those with at least **5,000** vehicles per day at the previous count and a previous count within **three years**. The base filter keeps the ranking off very low-volume roads, where a small absolute change reads as a large percentage. The recency filter keeps it off stale gaps, where a single annualized figure would not reflect current conditions. Segments outside the filter still appear in the output with their `yoy_growth_pct`, but with a blank `growth_rank`.

6. **Capacity flag.** `over_capacity` is true when the latest AADT is at or above the capacity threshold.

### Capacity threshold

The threshold is **10,000 vehicles per day**, stored in the output as the `capacity_threshold` column so the flag is self-documenting. It is a planning-level heuristic for an undivided two-lane rural highway: a daily volume high enough that road authorities commonly begin to study twinning or added capacity. It is not an official level-of-service standard, and several flagged segments on the 100-series highways are already multi-lane, so the flag marks high-volume corridors for review rather than literal over-capacity operation.

## Outputs

`out/corridor_ranking.csv`: one row per segment that has at least one valid AADT reading (953 segments in this snapshot), ordered busiest first. Every column is defined in data_dictionary.md. The golden copy is `expected/corridor_ranking.csv`.

## Edge cases

- **Several counts in one segment-year:** collapsed to the peak AADT.
- **Station-only or blank AADT rows:** dropped before any ranking.
- **Single-count segments:** ranked on AADT, blank growth, blank growth rank.
- **Long gap since the previous count:** growth is still computed and annualized, but the segment is left out of the growth ranking when the gap is over three years.
- **Low-volume segment with a large percentage swing:** ranked on AADT, growth shown, but left out of the growth ranking by the 5,000 base filter.
- **Tied AADT:** segments share an `aadt_rank`; `section_id` fixes the row order.

## Determinism

The snapshot is pinned and committed. Every result query ends in an `ORDER BY` with a unique tie-break, growth is rounded to two decimals, and the thresholds (10,000 capacity, 5,000 growth base, three-year recency) are fixed constants stated here. `expected/corridor_ranking.csv` was built from a first verified run; `python run.py` reproduces it byte for byte and prints PASS.
