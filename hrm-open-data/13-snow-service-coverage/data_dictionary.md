# Data dictionary

## Source columns used

### Street Winter Maintenance Areas (polygon)

| Column | Type | Meaning |
| --- | --- | --- |
| `SERVE_BY` | text | Body that services the area: `HRM`, `FED`, `PROV`, `HIAA` |
| `SERVAREA` | text | Service-area label |
| geometry | polygon | WGS84 area boundary |

### Sidewalk Winter Maintenance Areas (polygon)

| Column | Type | Meaning |
| --- | --- | --- |
| `MACHINE` | text | Service-zone description, unique per area |
| `FCODE` | text | Service-area code |
| geometry | polygon | WGS84 zone boundary |

### Ice Routes (polyline)

| Column | Type | Meaning |
| --- | --- | --- |
| `PRIORITY` | text | Snow-clearing priority: `1`, `2`, or null |
| `Shape__Length` | double | Segment length in metres (Web Mercator, EPSG:3857) |
| `OBJECTID` | integer | Stable sort key for the paged pull |
| geometry | polyline | WGS84 route line |

## Output: out/coverage_summary.csv (golden) and bi/exports/summary.csv

One long summary stacking three sections. The measure columns are blank where
they do not apply to a section.

| Column | Type | Meaning |
| --- | --- | --- |
| `section` | text | `street_by_serve_by`, `sidewalk_by_machine`, or `ice_by_priority` |
| `category` | text | The grouping value: a servicing body, a sidewalk zone, or a priority label |
| `feature_count` | integer | Number of source features in the group |
| `length_km` | decimal(12,2) | Ice-route length in km (sum of `Shape__Length`, metres, to km). Blank for polygon sections |
| `area_km2` | decimal(14,4) | Polygon ground area in km2 (`ST_Area_Spheroid`). Blank for the ice section |

Totals to check after import:

- Ice section: `length_km` reads 1724.03 (Priority 1), 1249.82 (Priority 2),
  4016.98 (unassigned); `feature_count` 7131, 5046, 6559 (18,736 total).
- Street section: `feature_count` sums to 32 (HRM 14, FED 11, PROV 6, HIAA 1).
- Sidewalk section: 23 rows, each `feature_count` 1.

## Map layers (bi/exports/, not part of the golden diff)

| File | Features | Properties |
| --- | --- | --- |
| `street_winter_areas.geojson` | 32 MultiPolygon | `area_id`, `serve_by`, `servarea`, `area_km2` |
| `sidewalk_winter_areas.geojson` | 23 MultiPolygon | `area_id`, `machine`, `fcode`, `area_km2` |
| `ice_routes_by_priority.geojson` | 3 MultiLineString | `priority`, `segment_count`, `length_km` |

Every polygon feature is promoted to `MultiPolygon` so each layer is one uniform
geometry type (Tableau refuses a mixed Polygon / MultiPolygon layer). `area_id`
is a unique per-area key for splitting marks in Tableau.

The ice layer is dissolved to one feature per priority; each feature's
`length_km` equals the golden's ice-section `length_km` for that priority.
