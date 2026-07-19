# Data dictionary: out/processing_summary.csv

One row per issuance stage and jurisdictional breakdown. Five rows, ordered by
`total_duration` descending. This is the golden summary that `run.py` verifies.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `issuance_stage` | text | Stage of the permit timeline: `Pre Issuance`, `Post Issuance`, or `Other Timeline`. | category |
| 2 | `jurisdictional_breakdown` | text | Who the time sits with: `Customer`, `Staff`, or `Other Type`. | category |
| 3 | `permit_count` | integer | Distinct permits in this stage-jurisdiction group. Equals the mart row count for the group, since the mart holds one row per permit here. | count |
| 4 | `total_duration` | number | Sum of `total_duration` across the group's permits, rounded to three decimals. | days |
| 5 | `avg_duration_per_permit` | number | `total_duration` divided by `permit_count`, rounded to three decimals. | days per permit |
| 6 | `median_duration` | number | Deterministic linear-interpolation median (`quantile_cont` at 0.5) of the group's per-permit durations, rounded to three decimals. | days |

## The duration unit

`Total_Duration` is the processing time HRM publishes for a permit at a given stage
and jurisdiction. The source field is a plain number and the dataset metadata carries
no explicit unit label. The values are fractional and range from 0 to about 2,028,
which is consistent with elapsed days for permit processing (a two-year Other Timeline
maps to roughly 720). This build therefore treats and labels the field as **days**.
The label does not alter any figure: every face reads `Total_Duration` exactly as
published, so the unit is a description of the number, not a conversion applied to it.

## Notes

- The five rows are the stage-jurisdiction combinations that occur in the snapshot;
  the theoretical 3x3 grid is not fully populated (for example `Other Timeline` occurs
  only with `Other Type`).
- The mean sits above the median in every group because the distribution is right
  skewed. Both are reported so neither hides the other.
