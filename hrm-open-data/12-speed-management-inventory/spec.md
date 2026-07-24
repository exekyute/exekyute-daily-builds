# Spec

## Purpose

Take three pinned snapshots of Halifax's speed-management geography, the Speed
Display Signs, the Traffic Control Locations, and the Neighbourhood Speed Limit
segments, and produce one per-device point mart plus two deterministic summaries:
how the point devices split by device type, and how the neighbourhood road network
splits by posted speed limit (segment count and kilometres). None of the three
layers carries a community column, so coverage is summarised by device type for the
points and by posted speed for the segments, not by community.

## Inputs

Three layers, all pulled 2026-07-13. See SOURCE.md.

- Speed Display Signs, `data/raw/hrm_speed-display-signs_2026-07-13.geojson`
  (73 point features).
- Traffic Control Locations,
  `data/raw/hrm_traffic-control-locations_2026-07-13.geojson` (707 point features).
- Neighbourhood Speed Limit,
  `data/raw/hrm_neighbourhood-speed-limit_2026-07-13.geojson` (13,835 polyline
  features).

Fields used: from the point layers, the coded device kind (`SIGNTYPE` /
`CONTROL_TYPE`), `INSTYR`, `LOCATION`, and the WGS84 point geometry; from the line
layer, `SPEED` and `Shape__Length`. All other source fields are not read.

## Schema and load (00_schema.sql, 01_load.sql)

The spatial extension is installed and loaded in `00_schema.sql` because the polyline
layer is read with `ST_Read`. Two raw landing tables are declared: `points_raw`
(source layer, coded device value, install year, location, lat, lon) and `lines_raw`
(posted speed, segment length in metres).

`01_load.sql` reads each point FeatureCollection with `read_json` and unnests the
features. The geometry is a `[longitude, latitude]` pair, and DuckDB list indexing is
1-based, so `coordinates[1]` is longitude and `coordinates[2]` is latitude. The two
point layers were pulled with `outSR=4326`, so the geometry is already WGS84 degrees.
The signs carry their device kind in `SIGNTYPE` (a string code); the control
locations carry it in `CONTROL_TYPE` (an integer code cast to VARCHAR) so both land
in one column. The polyline layer is read with `ST_Read`, which exposes each
feature's attributes as columns; only `SPEED` and `Shape__Length` are kept, because
the summary sums the published length rather than measuring the geometry.

## Cleaning and normalization (02_transform.sql)

1. **Whitespace.** The location text can carry stray line breaks, tabs, trailing
   spaces, and non-breaking spaces. A `norm` CTE folds every run of whitespace
   (including `chr(160)`) to a single space and trims each location once. One traffic
   control location ships with a trailing space, which the fold removes.
2. **Device decode.** The coded device value is mapped to its published domain
   label. Signs decode `SPDSGN` to `Speed Display Sign`; control locations map the
   `CONTROL_TYPE` integer to its traffic-control label (Signalized Intersection,
   Roundabout, and so on). The maps are the full published domains, so a code not
   seen in the current snapshot would still decode rather than silently drop.
3. **Types.** `install_year` is cast to INTEGER; an empty string becomes NULL and is
   kept as NULL, because many control locations carry no install year. Latitude and
   longitude are rounded to six decimals (about 0.1 m), ample for a city map and
   byte-stable in the CSV.
4. **No status filter.** All 780 point records are kept (73 signs, 707 control
   locations); no `ASSETSTAT` filter is applied, so the published counts stand.
5. **Lines.** Nothing needs cleaning: `speed_limit` is the posted limit (NULL where
   the source has none) and `len_m` is the published length in metres.

## Analysis (03_analysis.sql)

- **mart_points** (780 rows): the per-device map table, `source_layer`,
  `device_type`, `install_year`, `location`, `lat`, `lon`.
- **counts_by_device** (9 rows): `COUNT(*)` grouped by `source_layer` and
  `device_type`. One row for the signs (Speed Display Sign, 73) and eight for the
  control locations.
- **speed_by_limit** (13 rows): `COUNT(*)` and `round(SUM(len_m)/1000, 2)` grouped by
  `speed_limit`. The final row (blank speed) is the 156 segments with no posted
  limit.
- **headline**: three printed lines. Line one gives the total devices (780) and the
  sign / control split (73 / 707). Line two reads the control-type mix off
  `counts_by_device`. Line three gives the total posted road length (6,905.74 km
  across 13,835 segments) and the reduced-speed subset (410.41 km on 1,901 segments
  posted below the 50 km/h Nova Scotia urban default). The reduced-speed figures are
  computed from the raw metres (`speed_limit < 50` excludes the unposted NULL
  segments), not from the rounded per-speed rows, so they do not drift.

## Outputs

Three files, all golden and diffed row for row by `run.py verify`:

- `out/mart_points.csv` (golden, 780 rows). Order:
  `source_layer, device_type, install_year NULLS LAST, location, lat, lon`. The order
  reaches the six-decimal coordinates, so any two devices that share every earlier
  field still emit identical lines and the file stays byte-stable. Also copied to
  `bi/exports/mart_points.csv`.
- `out/counts_by_device.csv` (golden, 9 rows). Order:
  `source_layer, devices DESC, device_type`.
- `out/speed_by_limit.csv` (golden, 13 rows). Order: `speed_limit` ascending, blank
  (unposted) row last.

Two further files are written for the map, neither of them golden:

- `out/speed_devices.geojson`, the same 780 devices as point geometry
  (`ST_Point(lon, lat)`) with `source_layer`, `device_type`, `install_year`, and
  `location`, in the same order as the CSV mart. Copied to
  `bi/exports/speed_devices.geojson`.
- `bi/exports/speed_limits.geojson`, the line layer copied verbatim from the snapshot.

The devices are published as geometry rather than as `lat` and `lon` columns because
Tableau only offers its **Add a Marks Layer** target when the base map is driven by a
spatial field. With both layers spatial, the device points and the speed-limit lines
combine on one map; with a lat/lon base they cannot.

## Headline figures

- 780 point devices mapped: 73 speed display signs and 707 traffic control
  locations.
- Traffic control locations by type: 310 Signalized Intersection, 211 Rectangular
  Rapid Flashing Beacon, 153 RA-5 with Flashing Beacon, 14 Pedestrian Half Signals,
  9 Roundabout, 7 Overhead Flashing Beacon, 2 Lane Control, 1 Median Mounted
  Flashing Beacon.
- 6,905.74 km of posted neighbourhood speed limits across 13,835 segments.
- 410.41 km on 1,901 segments posted below the 50 km/h default (the reduced-speed
  streets).
- 156 segments (246.78 km) carry no posted limit in the source.

## Determinism

The three snapshots are pinned and committed. Every result query ends in an
`ORDER BY` that reaches a coordinate or a unique combination, so the row order is
fixed. Coordinates are rounded to six decimals and kilometres to two, so the same
snapshots always yield byte-identical output. No date arithmetic is used, so no
`CURRENT_DATE` appears anywhere; the pull date lives only in the snapshot filenames
and SOURCE.md. The three golden CSVs were frozen from a first verified run; `run.py`
re-runs the pipeline and diffs the fresh output against them, printing PASS only on
an exact row-for-row match.

## Edge cases

- **Uniform sign type.** All 73 speed display signs are one `SIGNTYPE` (`SPDSGN`), so
  the sign side of `counts_by_device` is a single row. The device-type breakdown that
  carries real variety is the eight-way control-location split.
- **Missing install years.** 497 of the 707 control locations and 2 of the 73 signs
  carry no install year. These are kept as blank `install_year`, ordered last within
  their device type; the build reports no install-year time series, matching the
  SINGLE (static coverage map) framing.
- **Unposted segments.** 156 of the 13,835 segments carry no `SPEED`. They form the
  final blank-speed row of `speed_by_limit` (246.78 km) and are excluded from the
  reduced-speed subset, which requires a posted limit below 50.
- **Rounding.** Each `total_km` row is independently rounded, so the visible rows sum
  to 6,905.75 while the headline total, computed from the raw metres, is 6,905.74.
  The headline and the numbers-match figure always use the raw-metres computation, the
  same one Tableau makes by summing `Shape__Length`.
- **Abbreviated duplicates.** A few sign records repeat a location with the street
  type spelled out and abbreviated (`Riverside Dr` and `Riverside Drive`) at the same
  coordinate. Both are kept as published, so the count stays 73.
