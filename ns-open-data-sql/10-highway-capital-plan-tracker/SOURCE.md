# Source

**Dataset:** Highway Improvement Plan

**Portal page:** https://data.novascotia.ca/Roads-Driving/Highway-Improvement-Plan/ax9v-hhtx

**Resource CSV:** https://data.novascotia.ca/resource/2h4d-zhi2.csv (roads) and https://data.novascotia.ca/resource/ch9v-3b2g.csv (bridges); see the id correction below.

**Socrata 4x4 id:** `ax9v-hhtx` (catalog entry; underlying tables `2h4d-zhi2` and `ch9v-3b2g`)

**Licence:** Open Government Licence - Nova Scotia. Attribution: contains information licensed under the Open Government Licence - Nova Scotia.

**Pull date:** 2026-07-06

**Snapshot:** `data/raw/ns_highway-improvement-plan_2026-07-06.csv`, 393 rows (337 roads + 56 bridges).

**Catalog idea:** #22.

## Id correction

The catalog id `ax9v-hhtx` resolves, but it points at a map visualization, not
a tabular dataset: its CSV export returns zero columns and zero rows. The map
is drawn from two underlying tabular datasets on the same portal, so the
snapshot combines both:

| Dataset | 4x4 id | Rows |
| --- | --- | --- |
| TIR Highway Improvement Plan - Roads | `2h4d-zhi2` | 337 |
| TIR Highway Improvement Plan - Bridges | `ch9v-3b2g` | 56 |

The parent ids come from the map's view metadata
(`/api/views/ax9v-hhtx.json`, under `series[].dataSource.datasetUid`).

## How the snapshot was pulled

The Socrata endpoint caps a default response at 1000 rows, so each dataset was
paged with `$limit=50000` and `$offset`, ordered by `project_de` for a stable
sort, until a short page came back. Both datasets fit in a single page. No app
token is needed for a one-off pull.

Geometry columns (`the_geom`, `shape__len`) were excluded through `$select`:
the model is tabular and the multiline geometries dwarf every other column. A
`source` column (`roads` or `bridges`) was added to record which dataset each
row came from. The combined result is saved as the dated snapshot above and
committed as the reproducibility anchor: `build.py` reads that file, never the
live endpoints.

## Columns in the source

| Column | Meaning |
| --- | --- |
| `project_de` | Project description, usually route and section |
| `km` | Planned length in kilometres (roads only) |
| `county` | County the project sits in |
| `project_ty` | Project grouping label with the fiscal year baked in |
| `construct_` | Project-type category (used as `type` in the model) |
| `year_start` | Fiscal year the project starts, for example `2025-2026` |
| `year_end` | Fiscal year the project ends |
| `status` | Project status as published |
| `source` | Added during the pull: `roads` or `bridges` |
