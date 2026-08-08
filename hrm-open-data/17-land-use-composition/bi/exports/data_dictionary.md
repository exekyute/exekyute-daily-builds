# BI exports

Two frozen files the BI tools read, both written by the SQL export step. Neither
tool recomputes anything on top of them.

## mart_landuse.csv

One row per community and land use class, 580 rows. Identical to
`out/mart_landuse.csv`.

| Column | BI type | Meaning |
| --- | --- | --- |
| `community` | Text | Community name (GSA_NAME), or `Unassigned` for 7 edge polygons. 183 values. Grouping and column field. |
| `zone_class` | Text | Broad land use class: Residential, Commercial, Mixed Use, Industrial, Park and Open Space, Institutional, Rural and Resource, Other, Unspecified. Colour and row field. 9 values. |
| `polygons` | Whole Number | Count of zoning polygons in that community and class. |
| `area` | Decimal Number | Zoned geodesic ground area, square kilometres, four decimals. Sum this; `Total Area = SUM(mart_landuse[area])`. |
| `area_share` | Decimal Number | The SQL's own share of the community's zoned area, percent, two decimals. The tools re-derive the same share from `area` (Tableau FIXED LOD, Power BI `Area Share`); this column is the reference. |

Reference figures (from the SQL golden): Bedford is the most mixed community, its
largest class at 30.59%; municipally Mixed Use leads at 40.20%, then Rural and
Resource 36.82%, Park and Open Space 14.84%, Residential 4.53%. Total zoned land
is about 3,637 km2.

## zoning_tagged.geojson

The 11,076 zoning polygons tagged for the Tableau choropleth, one feature per
polygon, WGS84 geometry at six decimal places. Connect as a Tableau Spatial file.

| Property | Type | Meaning |
| --- | --- | --- |
| `zone_class` | Text | Broad land use class; the map fill colour. |
| `community` | Text | Community the polygon's centroid falls in. |
| `zone` | Text | Raw `ZONE` code as published (reused across by-laws; the class is derived from the description). |
| `description` | Text | Zone label, whitespace-normalized. |
| `area_km2` | Number | Polygon geodesic ground area, square kilometres, four decimals. |
