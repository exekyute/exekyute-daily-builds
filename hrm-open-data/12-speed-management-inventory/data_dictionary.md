# Data dictionary

Columns used from the three source layers, and the columns of the three output
files. Source field types are from each layer's ArcGIS field metadata (`?f=json`).

## Source fields used

### Speed Display Signs (points)

| Field | Type | Meaning | Used |
| --- | --- | --- | --- |
| `OBJECTID` | integer | ArcGIS row id; also the pull sort key. | Ordering only |
| `SIGNTYPE` | text (coded) | Sign kind. Every record is `SPDSGN` (Speed Display Sign). | Yes, decoded to `device_type` |
| `INSTYR` | integer | Install year (2021 to 2025; two records blank). | Yes, `install_year` |
| `LOCATION` | text | Address or place description. | Yes, `location` |
| geometry | point | WGS84 point (`outSR=4326`). | Yes, `lat`, `lon` |
| `ASSETSTAT` | text (coded) | Asset status (61 `INS`, 12 `DIS`). | Read to note the split; not a filter |

### Traffic Control Locations (points)

| Field | Type | Meaning | Used |
| --- | --- | --- | --- |
| `OBJECTID` | integer | ArcGIS row id; also the pull sort key. | Ordering only |
| `CONTROL_TYPE` | integer (coded) | Control kind: 6 Signalized Intersection, 7 RA-5 with Flashing Beacon, 8 Overhead Flashing Beacon, 10 Rectangular Rapid Flashing Beacon, 11 Roundabout, 12 Lane Control, 14 Pedestrian Half Signals, 15 Median Mounted Flashing Beacon. | Yes, decoded to `device_type` |
| `INSTYR` | integer | Install year (2013 to 2026; 497 records blank). | Yes, `install_year` |
| `LOCATION` | text | Intersection or place description. | Yes, `location` |
| geometry | point | WGS84 point (`outSR=4326`). | Yes, `lat`, `lon` |

### Neighbourhood Speed Limit (polylines)

| Field | Type | Meaning | Used |
| --- | --- | --- | --- |
| `SPEED` | integer | Posted speed limit in km/h (20 to 110; 156 segments blank). | Yes, `speed_limit` |
| `Shape__Length` | double | Published segment length in metres. | Yes, summed to `total_km` |
| `STR_NAME`, `FULL_NAME`, `ST_CLASS` | text | Street name and class. | Not carried into the summary |
| geometry | polyline | WGS84 line, committed for Tableau to render. | `bi/exports/speed_limits.geojson` |

## out/mart_points.csv

One row per point device. 780 rows (73 signs + 707 control locations). This is also
the frozen point mart (`bi/exports/mart_points.csv`).

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `source_layer` | text | `Speed Display Sign` or `Traffic Control Location`. |
| 2 | `device_type` | text | Decoded device kind. Signs are all `Speed Display Sign`; control locations carry one of eight traffic-control labels. |
| 3 | `install_year` | integer | Install year; blank where the source carries none. |
| 4 | `location` | text | Address or intersection description, whitespace-normalized. |
| 5 | `lat` | number | Latitude, WGS84, six decimals. |
| 6 | `lon` | number | Longitude, WGS84, six decimals. |

Row order: `source_layer`, then `device_type`, then `install_year` (blanks last),
then `location`, then `lat`, then `lon`.

## out/counts_by_device.csv

Device counts by source layer and decoded device type. 9 rows.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `source_layer` | text | Source layer. |
| 2 | `device_type` | text | Decoded device kind. |
| 3 | `devices` | integer | Count of devices of that type. |

Row order: `source_layer`, then `devices` descending, then `device_type`. The counts
sum to 73 signs and 707 control locations, 780 in all.

## out/speed_by_limit.csv

Neighbourhood road segments and kilometres by posted speed limit. 13 rows.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `speed_limit` | integer | Posted limit in km/h; blank on the final row for the 156 segments with no posted limit. |
| 2 | `segments` | integer | Count of road segments at that limit. |
| 3 | `total_km` | number | Summed `Shape__Length` (metres) divided by 1000, two decimals. |

Row order: `speed_limit` ascending, with the blank (unposted) row last. The segment
counts sum to 13,835 and the kilometres to 6,905.74 (each row's `total_km` is
independently rounded, so the visible rows can differ from the total by a rounding
cent; the headline total is computed from the raw metres, not the rounded rows).
