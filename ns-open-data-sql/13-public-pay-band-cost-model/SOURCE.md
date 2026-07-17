# Source

**Dataset:** NS Government Pay Scales

**Portal page:** https://data.novascotia.ca/Public-Service/NS-Government-Pay-Scales/hn6q-5dmm

**Resource CSV:** https://data.novascotia.ca/resource/hn6q-5dmm.csv

**Socrata 4x4 id:** `hn6q-5dmm`

**Licence:** Open Government Licence - Nova Scotia. Attribution: contains information licensed under the Open Government Licence - Nova Scotia.

**Pull date:** 2026-07-06

**Snapshot:** `data/raw/ns_government-pay-scales_2026-07-06.csv`, 37,675 rows (the full dataset, every scale period from 2012 on).

**Catalog idea:** #6.

## How the snapshot was pulled

The Socrata endpoint caps a default response at 1000 rows, so the pull pages through with a stable sort on the row id:

    https://data.novascotia.ca/resource/hn6q-5dmm.csv?$order=:id&$limit=50000&$offset=0

The whole dataset is 37,675 rows, so a single 50000-row page returns everything; the paging loop stops when a page comes back short. No app token is needed for a one-off pull. The result is saved verbatim as the dated snapshot above and committed as the reproducibility anchor: `build.py` reads that file, never the live endpoint.

## Columns in the source

| Column | Meaning |
| --- | --- |
| `start_date` | First day the scale period applies |
| `end_date` | Last day the scale period applies |
| `pay_plan_type` | Plan grouping, for example Bargaining Unit |
| `pay_plan` | Classification code, for example ACC 01 |
| `pay_plan_level` | Step number inside the classification; the EC, LM, and SO plans label their below-range steps 80 to 99 ahead of label 0, so raw label order is not pay order |
| `biweekly_pay_rate` | Published biweekly rate in dollars at that step |
| `hourly_pay_rate` | Published hourly rate, filled only for some records |

The `hn6q-5dmm` id resolved on the pull date and returned the expected columns, so no id correction was needed. The model uses the latest scale period in the snapshot (start_date 2025-04-01, running to 2026-03-31); earlier periods stay in the snapshot untouched.
