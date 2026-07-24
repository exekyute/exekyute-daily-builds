# Source

Three layers from Halifax Open Data (the Halifax Data Mapping and Analytics Hub),
each pulled from its ArcGIS REST FeatureServer as GeoJSON.

## Datasets

| Layer | Slug | Item id | Service | Geometry | Rows |
| --- | --- | --- | --- | --- | --- |
| Street Winter Maintenance Areas | `HRM::street-winter-maintenance-areas` | `91ff9b57ecc54e59997f3e12b08f6895` | `Street_Winter_Maintenance_Areas` | polygon | 32 |
| Sidewalk Winter Maintenance Areas | `HRM::sidewalk-winter-maintenance-areas` | `d1d5a8f9eb0f4e0a81fda53858fa9b1f` | `Sidewalk_Winter_Maintenance_Areas` | polygon | 23 |
| Ice Routes | `HRM::ice-routes` | `e9dd1561e22e4a149c5b45f54ec0942d` | `Ice_Routes` | polyline | 18,736 |

**REST base:** `https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/<Service>/FeatureServer/0/query`

**Licence:** Open Government Licence, Halifax. Attribution: Contains information licenced under the Open Government Licence, Halifax. Licence text: https://data-hrm.hub.arcgis.com/pages/open-data-licence.

**Pull date:** 2026-07-13

**Snapshots (committed):**

- `data/raw/hrm_street-winter-maintenance-areas_2026-07-13.geojson`, 32 features.
- `data/raw/hrm_sidewalk-winter-maintenance-areas_2026-07-13.geojson`, 23 features.
- `data/raw/hrm_ice-routes_2026-07-13.geojson`, 18,736 features.

**Catalog idea:** #26.

## How the snapshots were pulled

Each layer was requested as GeoJSON (`f=geojson`, WGS84) with all fields:

    <base>/<Service>/FeatureServer/0/query?where=1=1&outFields=*&f=geojson

The two polygon layers return in a single response (32 and 23 features, both under
the 2000-row per-request cap). Ice Routes has 18,736 features, so it was paged
with `resultOffset` and `resultRecordCount=2000` and a stable `orderByFields=OBJECTID`,
ten pages in all, then concatenated in OBJECTID order:

    <base>/Ice_Routes/FeatureServer/0/query?where=1=1&outFields=*&f=geojson&orderByFields=OBJECTID&resultRecordCount=2000&resultOffset=<0,2000,...,18000>

No app token or sign-in is needed for public read. `run.py` reads the committed
snapshots, never the live endpoint.

**Ice-route coordinate precision.** The Ice Routes snapshot was saved with its
line coordinates rounded to six decimal places (about 0.1 m at this latitude) to
keep the committed file to a reasonable size. That rounding touches only the
drawn geometry, not the `Shape__Length` attribute or any other field, so the
tabular golden, which is summed from `Shape__Length`, is unaffected. The two
small polygon snapshots are kept at full source precision.

## A note on ice-route length units

`Shape__Length` is the Ice Routes layer's own stored length field. The layer is
served in Web Mercator (EPSG:3857), so `Shape__Length` is in projected metres,
which overstate true ground distance by roughly the secant of the latitude (about
1.4 at Halifax, around 44.6 degrees north). The golden sums `Shape__Length` as
provided, because that is the field a viewer sums in Tableau off the same
GeoJSON, so the SQL golden and the map summary agree to the metre.

For reference, `ST_Length_Spheroid` measured on the WGS84 geometry gives the true
ground length:

| Priority | `Shape__Length` km (golden) | `ST_Length_Spheroid` km (true ground) |
| --- | --- | --- |
| 1 | 1,724.03 | 1,202.25 |
| 2 | 1,249.82 | 861.99 |
| (unassigned) | 4,016.98 | 2,778.18 |

The build reports the `Shape__Length` figures because the numbers-match contract
is tool-to-tool consistency on the same field; the spheroid column is recorded
here so the projection effect is documented rather than hidden.

## Fields used

**Street Winter Maintenance Areas**

| Column | Meaning |
| --- | --- |
| `SERVE_BY` | Body that services the area (HRM, FED, PROV, HIAA) |
| `SERVAREA` | Service-area label |
| geometry | WGS84 polygon |

**Sidewalk Winter Maintenance Areas**

| Column | Meaning |
| --- | --- |
| `MACHINE` | Service-zone description (unique per area) |
| `FCODE` | Service-area code |
| geometry | WGS84 polygon |

**Ice Routes**

| Column | Meaning |
| --- | --- |
| `PRIORITY` | Snow-clearing priority: `1`, `2`, or null (no numbered priority) |
| `Shape__Length` | Segment length in metres (Web Mercator, EPSG:3857) |
| `OBJECTID` | Stable sort key for the paged pull |
| geometry | WGS84 polyline |

`ROUTE_NAME`, `MATERIAL`, `EQUIPMENT`, `MAINTENANCE`, `SACC`, `SOURCE`, and the
date fields are present in the source but not used by the summary.
