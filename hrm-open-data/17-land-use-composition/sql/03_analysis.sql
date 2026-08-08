-- 03_analysis.sql
-- Three result tables plus a headline, all built on the tagged polygons.
-- Area is the true geodesic ground area (ST_Area_Spheroid on the WGS84
-- geometry), summed exactly as DECIMAL and reported in square kilometres. One
-- polygon is one zoning record at one place; a community's total zoned area is
-- the sum of its polygons.

-- Table A (mart): the land-use composition, one row per community and zone_class
-- with the polygon count, the zoned area in square kilometres, and that class's
-- share of the community's total zoned area, to two decimals. This is the frozen
-- mart both BI tools read. Unassigned (7 edge polygons) is kept as its own
-- community so no area is lost.
CREATE TABLE mart_landuse AS
WITH agg AS (
  SELECT community, zone_class, COUNT(*) AS polygons, SUM(area_m2) AS a_m2
  FROM zoning_tagged
  GROUP BY community, zone_class
),
tot AS (
  SELECT community, SUM(a_m2) AS community_m2
  FROM agg
  GROUP BY community
)
SELECT
  agg.community,
  agg.zone_class,
  agg.polygons,
  CAST(ROUND(agg.a_m2 / 1000000.0, 4) AS DECIMAL(14,4)) AS area,
  CAST(ROUND(100.0 * agg.a_m2 / tot.community_m2, 2) AS DECIMAL(7,2)) AS area_share
FROM agg
JOIN tot USING (community);

-- Table B (mix ranking): one row per real community with its class count, total
-- zoned area, dominant class and that class's share, and a mix index defined as
-- one hundred minus the largest class share (a percentage): the more evenly the
-- land is split across classes, the smaller the largest share and the higher the
-- mix index. community_mix_rank 1 is the most mixed community. The Unassigned
-- edge bucket is not a real community and is excluded from the ranking.
CREATE TABLE community_mix_ranking AS
WITH totals AS (
  SELECT community, COUNT(*) AS classes, SUM(area) AS total_area
  FROM mart_landuse
  WHERE community <> 'Unassigned'
  GROUP BY community
),
dominant AS (
  SELECT community, zone_class AS dominant_class, area_share AS largest_class_share
  FROM mart_landuse
  WHERE community <> 'Unassigned'
  QUALIFY ROW_NUMBER() OVER (PARTITION BY community ORDER BY area_share DESC, zone_class) = 1
),
joined AS (
  SELECT
    t.community,
    t.classes,
    CAST(ROUND(t.total_area, 4) AS DECIMAL(14,4)) AS total_area,
    d.dominant_class,
    d.largest_class_share,
    CAST(100.00 - d.largest_class_share AS DECIMAL(7,2)) AS mix_index
  FROM totals t
  JOIN dominant d USING (community)
)
SELECT
  DENSE_RANK() OVER (ORDER BY mix_index DESC) AS community_mix_rank,
  community,
  classes,
  total_area,
  dominant_class,
  largest_class_share,
  mix_index
FROM joined;

-- Table C (municipal composition): the land-use mix for the whole municipality,
-- one row per zone_class with polygon count, zoned area, and share of all HRM
-- zoned land. This is the context the per-community shares sit inside.
CREATE TABLE class_area_overall AS
WITH agg AS (
  SELECT zone_class, COUNT(*) AS polygons, SUM(area_m2) AS a_m2
  FROM zoning_tagged
  GROUP BY zone_class
),
tot AS (SELECT SUM(a_m2) AS total_m2 FROM agg)
SELECT
  agg.zone_class,
  agg.polygons,
  CAST(ROUND(agg.a_m2 / 1000000.0, 4) AS DECIMAL(14,4)) AS area,
  CAST(ROUND(100.0 * agg.a_m2 / tot.total_m2, 2) AS DECIMAL(7,2)) AS area_share
FROM agg CROSS JOIN tot;

-- Table D (headline): the two ready-to-print lines run.py echoes. Line one is
-- the municipal frame (polygon count, class count, community count, and the
-- leading class with its municipal share); line two is the most mixed community
-- with its largest class share and class count. run.py prints these; it does not
-- compute them.
CREATE TABLE headline AS
WITH frame AS (
  SELECT
    (SELECT COUNT(*) FROM zoning_tagged) AS polys,
    (SELECT COUNT(*) FROM class_area_overall) AS classes,
    (SELECT COUNT(*) FROM community_mix_ranking) AS communities
),
lead_class AS (
  SELECT zone_class, area_share
  FROM class_area_overall
  ORDER BY area_share DESC, zone_class
  LIMIT 1
),
top_mix AS (
  SELECT community, largest_class_share, classes
  FROM community_mix_ranking
  WHERE community_mix_rank = 1
  ORDER BY community
  LIMIT 1
)
SELECT 1 AS ord,
  'HRM zoning holds ' || (SELECT polys FROM frame) || ' land use polygons across '
    || (SELECT communities FROM frame) || ' communities and '
    || (SELECT classes FROM frame) || ' land use classes; '
    || (SELECT zone_class FROM lead_class) || ' leads municipally at '
    || (SELECT area_share FROM lead_class) || '% of zoned land.' AS line
UNION ALL
SELECT 2 AS ord,
  'Most mixed community: ' || (SELECT community FROM top_mix) || ', where the largest zone class holds only '
    || (SELECT largest_class_share FROM top_mix) || '% of its zoned area across '
    || (SELECT classes FROM top_mix) || ' classes.' AS line
ORDER BY ord;
