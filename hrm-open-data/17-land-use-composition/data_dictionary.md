# Data dictionary

## out/mart_landuse.csv

One row per community and land use class: that class's zoned area and its share
of the community's total zoned area. 580 rows. This is also the frozen BI mart
(`bi/exports/mart_landuse.csv`).

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `community` | text | Community name (GSA_NAME), or `Unassigned` for the 7 edge polygons whose centroid falls outside every boundary. |
| 2 | `zone_class` | text | Broad land use class: one of Residential, Commercial, Mixed Use, Industrial, Park and Open Space, Institutional, Rural and Resource, Other, Unspecified. See spec.md. |
| 3 | `polygons` | integer | Count of zoning polygons in that community and class. |
| 4 | `area` | number | Zoned geodesic ground area in square kilometres, four decimals. |
| 5 | `area_share` | number | This class's share of the community's total zoned area, percent, two decimals. |

Row order: `community`, then `zone_class`.

## out/community_mix_ranking.csv

Real communities ranked by how mixed their land use is. 182 rows (Unassigned
excluded).

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `community_mix_rank` | integer | Dense rank by `mix_index` descending. 1 is the most mixed community. |
| 2 | `community` | text | Community name. |
| 3 | `classes` | integer | Number of distinct land use classes present in the community. |
| 4 | `total_area` | number | Community's total zoned area, square kilometres, four decimals. |
| 5 | `dominant_class` | text | The single largest land use class in the community. |
| 6 | `largest_class_share` | number | The dominant class's share of the community's zoned area, percent, two decimals. |
| 7 | `mix_index` | number | `100 - largest_class_share`; higher means more evenly mixed. |

Row order: `community_mix_rank`, then `community`.

## out/class_area_overall.csv

The municipal land use mix, one row per class. 9 rows.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `zone_class` | text | Broad land use class. |
| 2 | `polygons` | integer | Count of zoning polygons in that class across HRM. |
| 3 | `area` | number | Class's total geodesic area, square kilometres, four decimals. |
| 4 | `area_share` | number | Class's share of all HRM zoned land, percent, two decimals. |

Row order: `area_share` descending, then `zone_class`.

## bi/exports/zoning_tagged.geojson

The 11,076 zoning polygons tagged for the Tableau choropleth, one feature per
polygon with WGS84 geometry at six decimals. See `bi/exports/data_dictionary.md`.

| Property | Type | Meaning |
| --- | --- | --- |
| `zone_class` | text | Broad land use class (the map colour). |
| `community` | text | Community the polygon's centroid falls in. |
| `zone` | text | Raw `ZONE` code as published. |
| `description` | text | Zone label, whitespace-normalized. |
| `area_km2` | number | Polygon geodesic ground area, square kilometres, four decimals. |
