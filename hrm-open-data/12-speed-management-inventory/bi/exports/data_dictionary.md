# BI exports: speed management inventory

Three frozen files, all written by the SQL pipeline. The map connects to the two
spatial files; the CSV is the readable copy of the same 780 devices.

- `speed_devices.geojson`, the device layer (point geometry).
- `speed_limits.geojson`, the street layer (line geometry), the committed
  neighbourhood speed-limit snapshot.
- `mart_points.csv`, identical to `out/mart_points.csv`, the golden mart.

Both map layers are spatial on purpose. Tableau offers the **Add a Marks Layer** drop
target only when the base map is driven by a spatial field, so a map built from plain
`lat` and `lon` columns cannot take the second layer.

## speed_devices.geojson

The device layer, 780 point features (73 speed display signs + 707 traffic control
locations). Same rows and same order as `mart_points.csv`, with the coordinates
carried as real point geometry instead of two number columns.

| Field | Tableau type | Meaning |
| --- | --- | --- |
| `Geometry` | Spatial | The device point, WGS84. Double-click to draw the base map. |
| `device_id` | Whole Number | Stable key 1 to 780, numbered by the same order as the CSV mart. Put it on **Detail**. Tableau aggregates a spatial layer with `COLLECT(Geometry)`, so without a unique field on Detail the 780 points collapse into a couple of dozen grouped marks. |
| `source_layer` | Text | `Speed Display Sign` or `Traffic Control Location`. Shape field. 2 values. |
| `device_type` | Text | Decoded device kind. Colour field. 9 values. |
| `install_year` | Whole Number | Install year; null on 499 devices. Not used in a time series. |
| `location` | Text | Address or intersection description. Tooltip field. |

Use `speed_devices.geojson (Count)` for the device total: 780 unfiltered, 73 on
`source_layer = Speed Display Sign`, 707 on `Traffic Control Location`. With
`device_id` on Detail the status-bar mark count also reads 780.

## mart_points.csv

One row per point device, 780 rows (73 speed display signs + 707 traffic control
locations). The readable copy and the golden mart. The map builds from
`speed_devices.geojson` instead, so these `lat` and `lon` columns are for reading and
checking, not for plotting.

| Column | Tableau type | Meaning |
| --- | --- | --- |
| `source_layer` | Text | `Speed Display Sign` or `Traffic Control Location`. Shape field on the map. 2 values. |
| `device_type` | Text | Decoded device kind. Signs are all `Speed Display Sign`; control locations carry one of eight labels. Colour field on the map. 9 values. |
| `install_year` | Whole Number | Install year; blank where the source carries none (2 signs, 497 control locations). Not used in a time series. |
| `location` | Text | Address or intersection description. Tooltip field. |
| `lat` | Decimal Number | Latitude, WGS84, six decimals. Latitude role in Tableau. |
| `lon` | Decimal Number | Longitude, WGS84, six decimals. Longitude role in Tableau. |

Count `mart_points` (or a row count) for the device total: 780 with no filter, 73 on
`source_layer = Speed Display Sign`, 707 on `Traffic Control Location`.

## speed_limits.geojson

The neighbourhood speed-limit line layer, 13,835 polyline segments. Tableau reads it
as a spatial file and generates a **Geometry** field; the two attributes the map uses
are below.

| Field | Tableau type | Meaning |
| --- | --- | --- |
| `Geometry` | Spatial | The road-segment line. Drag onto the map to add the street marks layer. |
| `SPEED` | Whole Number | Posted speed limit in km/h (20 to 110; blank on 156 segments). Colour field on the line layer; filter to at most 49 for the reduced-speed streets. |
| `Shape__Length` | Decimal Number | Segment length in metres. `SUM(Shape__Length) / 1000` gives kilometres. |

Reference figures (from the SQL golden): 780 point devices (73 signs, 707 control
locations); traffic control locations 310 Signalized Intersection, 211 Rectangular
Rapid Flashing Beacon, 153 RA-5 with Flashing Beacon, 14 Pedestrian Half Signals,
9 Roundabout, 7 Overhead Flashing Beacon, 2 Lane Control, 1 Median Mounted Flashing
Beacon; 6,905.74 km of posted speed limits across 13,835 segments, of which 410.41 km
on 1,901 segments are posted below the 50 km/h default; 156 segments (246.78 km)
carry no posted limit.
