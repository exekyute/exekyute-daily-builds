# Data dictionary: mart_processing.csv

The frozen mart both BI faces read. One row per permit per issuance stage per
jurisdictional breakdown. 149,705 rows, ordered by `permit_number`, then
`issuance_stage`, then `jurisdictional_breakdown`. The SQL export step writes this
file; Tableau and Power BI recompute nothing, they only read it.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `permit_number` | text | Permit identifier. Appears on several rows, one per stage and jurisdiction the permit touched. | id |
| 2 | `issuance_stage` | text | Stage of the permit timeline: `Pre Issuance`, `Post Issuance`, or `Other Timeline`. | category |
| 3 | `jurisdictional_breakdown` | text | Who the time sits with: `Customer`, `Staff`, or `Other Type`. | category |
| 4 | `total_occurrence` | integer | Count of occurrences aggregated into this row, as published. | count |
| 5 | `total_duration` | number | Processing time for this permit, stage, and jurisdiction. One value per row, which is what gives each stage a distribution the box plot can draw. | days |

## The duration unit

`total_duration` is the processing time HRM publishes for a permit at a given stage
and jurisdiction. The source field is a plain number and the dataset metadata carries
no explicit unit label. The values are fractional and range from 0 to about 2,028,
consistent with elapsed days for permit processing (a two-year Other Timeline maps to
roughly 720). This build treats and labels the field as **days**. The label does not
alter any figure: every face reads `total_duration` exactly as published, so the unit
describes the number rather than converting it.

## Grain and its consequence

Because there is one row per permit per stage per jurisdiction, `total_duration` is a
per-permit value, not a pre-aggregated total. That is deliberate: a stage such as Pre
Issuance holds thousands of individual permit durations, so a box plot over the rows
shows the real median and quartile spread, and a sum over the rows equals the stage's
total time. A permit can appear under both `Customer` and `Staff` inside one stage, so
counting distinct permits within a stage is not the same as counting the rows; use
`DISTINCTCOUNT(permit_number)` when a per-permit denominator is wanted.
