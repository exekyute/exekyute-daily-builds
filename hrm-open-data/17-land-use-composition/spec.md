# Spec

## Purpose

Take pinned GeoJSON snapshots of Halifax's Zoning Boundaries and Community
Boundaries and produce one per-community-and-class mart plus two deterministic
ranking tables that answer: what share of each community's land carries each
broad land use class, and which communities are the most mixed. Every zoning
polygon is folded into one of eight broad classes and assigned to the community
that contains its centroid.

## Inputs

- Zoning Boundaries (`HRM::zoning-boundaries`), pulled to
  `data/raw/hrm_zoning-boundaries_2026-07-13.geojson` (11,076 polygons).
- Community Boundaries / GSA (`HRM::community-boundaries`), pulled to
  `data/raw/hrm_community-boundaries_2026-07-13.geojson` (200 polygons).

See SOURCE.md. Fields used: `ZONE`, `DESCRIPTION`, and the polygon geometry from
zoning; `GSA_NAME` and the polygon geometry from the community layer. `OBJECTID`
is a stable sort key only. `Shape__Area` is deliberately not used; area is
geodesic (see below).

## Load (01_load.sql)

`ST_Read` reads each committed GeoJSON into a table, exposing the attributes as
columns and the polygon as a `geom` GEOMETRY column in WGS84 (EPSG:4326). The
spatial extension is installed and loaded in 00_schema and stays loaded for the
connection.

## Area basis: geodesic, not Shape__Area

The zoning service stores geometry in Web Mercator (EPSG:3857), whose area is
inflated by roughly three times at Halifax's latitude, so the carried
`Shape__Area` overstates ground area (about 10,633 km2 vs a true 3,637 km2). Area
here is the true geodesic ground area of each polygon on the WGS84 spheroid,
`ST_Area_Spheroid(geom)`, carried as an exact `DECIMAL(18,4)` in square metres so
every downstream `SUM` is order-independent and the golden output is byte-stable.
Land use shares are ratios and are within a few hundredths of a percent under
either basis; the geodesic basis makes the absolute square-kilometre figures
honest.

## Cleaning and the spatial join (02_transform.sql)

1. **Whitespace.** `DESCRIPTION` is folded (every run of whitespace including the
   non-breaking space `chr(160)` collapsed to a single space, then trimmed), so a
   stray line break or trailing space cannot defeat a keyword match or split a
   later CSV row. The uppercased normalized text `d` drives the keyword rules.

2. **zone_class.** An ordered `CASE` folds each polygon into one of eight broad
   classes, or `Unspecified` when `ZONE` is null. The rule set is below.

3. **Community assignment.** Zoning has no community column, so each polygon is
   assigned to the GSA whose boundary contains the polygon's centroid,
   `ST_Within(ST_Centroid(zoning.geom), gsa.geom)`. A centroid outside every
   boundary (7 polygons) is labelled `Unassigned`. A `QUALIFY ROW_NUMBER()` guard
   keeps the result one row per polygon even if two boundaries were to overlap.

### The zone_class mapping

The raw `ZONE` code carries 206 distinct values plus a null, and the same code is
reused across land use by-laws with different meanings (`C-5` is "Mixed Use" in
one by-law and "Harbour Related Industrial" in another). The plain-language
`DESCRIPTION` is therefore the primary signal, matched by keyword, with the
`ZONE` code as a secondary and fallback signal for a handful of families. The
`CASE` is evaluated top to bottom and the first matching branch wins, so the
order resolves the overlaps:

| Order | Class | Matches when the description (or noted zone code) contains |
| --- | --- | --- |
| 1 | `Unspecified` | `ZONE` is null |
| 2 | `Industrial` | INDUSTR, SALVAGE, MATERIALS, AEROTECH, AIRPORT, EMPLOYMENT, BUSINESS PARK, BUSINESS CAMPUS, BUSINESS INDUSTRY; excluding FISHING and TOURIST |
| 3 | `Rural and Resource` | RURAL, RESOURCE, FISHING, RURAL SETTLEMENT, EQUINE, AGRICULT; or zone code starts `MR` or equals `RE` |
| 4 | `Mixed Use` | MIXED USE, MIXED-USE, LIVE-WORK, MIXED OPPORTUNITY, CORRIDOR, DOWNTOWN; or RESIDENTIAL together with COMMERCIAL or BUSINESS; or zone code in CEN-1, CEN-2, BW-CEN, US |
| 5 | `Institutional` | INSTITUTIONAL, UNIVERSITY, COLLEGE, HOSPITAL, DND, NATIONAL DEFEN, CULTURAL, COMMUNITY FACILITY/FACILITIES, SPECIAL FACILITY, EXHIBITION, UTILITIES, or zone code S/SI; excluding any with PARK |
| 6 | `Commercial` | COMMERCIAL, BUSINESS, SHOPPING, RETAIL, TOURIST, LARGE SCALE, MAINSTREET, MAIN STREET; excluding any with DWELLING |
| 7 | `Residential` | RESIDENTIAL, DWELLING, SINGLE FAMILY, SINGLE UNIT, TWO FAMILY, TWO UNIT, TOWNHOUSE, MULTIPLE, MULTI-UNIT, MULTI UNIT, APARTMENT, CLUSTER, MOBILE, HOUSING, HOME OCCUPATION, HOME BUSINESS |
| 8 | `Park and Open Space` | PARK, OPEN SPACE, CONSERVATION (not HERITAGE), RECREATION, FLOODPLAIN, FLOODWAY, FLOOD PLAIN, PRESERVATION, PRESERVE, PROTECTED, WATER SUPPLY, WATER ACCESS, ENVIRONMENTAL, ISLANDS, HAZARD, COASTAL, WESTERN COMMON |
| 9 | `Other` | anything unmatched (Comprehensive Development Districts, Holding, Urban and Transportation Reserves, Downsview Complex, village centres, and the four zone codes with no description) |

Why the order resolves the false friends:

- **Industrial before Mixed Use and Rural** so "Mixed Industrial" and "Harbour
  Related Industrial" land in Industrial, while the FISHING and TOURIST carve-outs
  keep "Fishing Industry" in Rural and Resource and "Tourist Industry" in
  Commercial rather than Industrial.
- **Rural and Resource before Mixed Use and Residential** so "Mixed Resource" and
  every "Rural Residential" land in Rural and Resource, not Mixed Use or
  Residential. The `MR` prefix keeps the Mixed Resource family (including the one
  polygon labelled "Mixed Use 1") together.
- **Mixed Use before Commercial and Residential** so a combined
  "Residential/Minor Commercial" zone and the downtown, corridor, and centre
  designations read as Mixed Use.
- **Institutional excludes PARK** so "Park and Institutional" and
  "Park/Institutional" fall through to Park and Open Space, while
  "Institutional, Cultural and Open Space" stays Institutional.
- **Commercial excludes DWELLING** so "Auxiliary Dwelling with Home Business"
  reads as Residential, not Commercial.
- **Conservation excludes HERITAGE** so "Heritage Conservation District" is not
  miscounted as open space.

The mapping is an ordered set of literal keyword and exact-code tests on the
whitespace-normalized, uppercased description, so it is fully deterministic. The
raw `ZONE` and `DESCRIPTION` are kept beside the derived class in
`bi/exports/zoning_tagged.geojson`.

## Analysis (03_analysis.sql)

- **mart_landuse**: one row per community and zone_class with the polygon count,
  the geodesic area in square kilometres, and that class's `area_share` of the
  community's total zoned area (percent, two decimals). This is the frozen mart.
- **community_mix_ranking**: one row per real community (Unassigned excluded)
  with its class count, total zoned area, dominant class, that class's share, and
  a `mix_index = 100 - largest_class_share`. The more evenly the land splits
  across classes, the smaller the largest share and the higher the index.
  `community_mix_rank` is a `DENSE_RANK` on the index descending; rank 1 is the
  most mixed.
- **class_area_overall**: one row per zone_class for the whole municipality with
  polygon count, area, and share of all HRM zoned land.
- **headline**: two ready-to-print lines. `run.py` prints them; it does not
  compute them.

## Outputs

Three golden CSVs, diffed row for row by `run.py verify`, plus one geometry
export:

- `out/mart_landuse.csv` (golden, 580 rows). `ORDER BY community, zone_class`.
  Also copied to `bi/exports/mart_landuse.csv` for the two BI tools.
- `out/community_mix_ranking.csv` (golden, 182 rows).
  `ORDER BY community_mix_rank, community`.
- `out/class_area_overall.csv` (golden, 9 rows).
  `ORDER BY area_share DESC, zone_class`.
- `bi/exports/zoning_tagged.geojson` (11,076 polygon features), each tagged with
  `zone_class`, `community`, `zone`, `description`, and `area_km2`, geometry at
  six decimals, for the Tableau choropleth. Written by the SQL export step because
  it needs the spatial engine.

## Headline figures

- 11,076 zoning polygons across 182 communities and 9 land use classes (eight
  broad classes plus Unspecified), on about 3,637 km2 of zoned land.
- Municipal mix: Mixed Use leads at 40.20% of zoned land, then Rural and Resource
  36.82%, Park and Open Space 14.84%, Residential 4.53%, Other 1.93%, Industrial
  1.31%, Institutional 0.22%, Commercial 0.15%. Mixed Use is HRM's own regional
  by-law designation `MU`, which covers large suburban and rural-fringe areas.
- Most mixed community: Bedford, where the largest single class holds only 30.59%
  of its zoned area across all 8 classes. Its Other bucket (master-planned
  Comprehensive Development Districts) at 30.59% barely edges out Residential at
  30.07%. Next are Halifax at 32.40% (Residential) and Lower Sackville at 33.21%
  (Residential).

## Determinism

The snapshots are pinned and committed. Areas are summed as exact DECIMAL so the
result is order-independent; every result query ends in an `ORDER BY`. The
centroid assignment is a single deterministic point-in-polygon test per polygon
with a stable tie-break, so the same snapshots always yield byte-identical
output. The three golden CSVs were frozen from a first verified run; `run.py`
re-runs the pipeline and diffs the fresh output against them, printing PASS only
on an exact row-for-row match.

## Edge cases

- **Reused zone codes:** the same `ZONE` code carries different meanings across
  by-laws, so the description drives the class and the code is only a fallback.
- **Null zone code:** one polygon has a null `ZONE` and is reported as its own
  `Unspecified` class rather than dropped.
- **Unassigned polygons:** 7 polygons whose centroid falls outside every
  community boundary are kept under the `Unassigned` community in the mart so no
  area is lost, and excluded from the mix ranking, which ranks real communities.
- **Communities with no zoning:** 18 of the 200 communities carry no zoning
  polygon centroid and simply do not appear in the mart; a community with no
  zoned land has no composition to report.
- **Village centres and CDDs:** small rural village centres and Comprehensive
  Development Districts do not resolve to a single conventional land use and are
  reported honestly under `Other` rather than force-fit into one class.
