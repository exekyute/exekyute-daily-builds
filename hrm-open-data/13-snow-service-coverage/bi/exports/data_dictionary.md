# BI exports data dictionary

Frozen layers written by the SQL export step (`sql/99_export.sql`) for the single
Tableau dashboard. The Tableau map reads these directly; it recomputes nothing.

## summary.csv

A copy of the tabular golden `out/coverage_summary.csv`. One long summary
stacking three sections; the measure columns are blank where they do not apply.

| Column | Type | Meaning |
| --- | --- | --- |
| `section` | text | `street_by_serve_by`, `sidewalk_by_machine`, or `ice_by_priority` |
| `category` | text | Grouping value: servicing body, sidewalk zone, or priority label |
| `feature_count` | integer | Number of source features in the group |
| `length_km` | number | Ice-route length in km (sum of `Shape__Length`, metres). Blank for polygons |
| `area_km2` | number | Polygon ground area in km2 (`ST_Area_Spheroid`). Blank for the ice section |

## street_winter_areas.geojson (32 MultiPolygon features)

| Property | Type | Meaning |
| --- | --- | --- |
| `area_id` | integer | Unique per-area id (source OBJECTID); use on Tableau Detail to split marks |
| `serve_by` | text | Servicing body: HRM, FED, PROV, HIAA |
| `servarea` | text | Service-area label (repeats: all federal areas share DND) |
| `area_km2` | number | Ground area of the polygon in km2 |

## sidewalk_winter_areas.geojson (23 MultiPolygon features)

| Property | Type | Meaning |
| --- | --- | --- |
| `area_id` | integer | Unique per-area id (source OBJECTID) |
| `machine` | text | Service-zone description (unique per area) |
| `fcode` | text | Service-area code |
| `area_km2` | number | Ground area of the polygon in km2 |

## ice_routes_by_priority.geojson (3 MultiLineString features)

| Property | Type | Meaning |
| --- | --- | --- |
| `priority` | text | `1`, `2`, or `(unassigned)` |
| `segment_count` | integer | Number of source route segments in the priority |
| `length_km` | number | Priority length in km (sum of `Shape__Length`, metres) |

## Totals to check after import

- Ice `length_km`: 1724.03 (Priority 1), 1249.82 (Priority 2), 4016.98 (unassigned).
- Ice `segment_count`: 7131, 5046, 6559 (18,736 total).
- Street `feature_count` sums to 32 (HRM 14, FED 11, PROV 6, HIAA 1).
- Sidewalk: 23 features, each `feature_count` 1.
