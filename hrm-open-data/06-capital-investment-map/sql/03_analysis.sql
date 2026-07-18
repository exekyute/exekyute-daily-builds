-- 03_analysis.sql
-- Three count questions plus a headline. This dataset carries no dollar or
-- budget amount, so every measure is a count of capital-project records, never
-- a spend. One record is one project at one location in one budget year.

-- Question A: how many project records fall under each normalized category in
-- each budget year? This is the category-by-year grid the area chart is built
-- on.
CREATE TABLE counts_by_category_year AS
SELECT
  category_norm,
  year,
  COUNT(*) AS projects
FROM cap_clean
GROUP BY category_norm, year;

-- Question B: how many project records carry each asset type? Most records
-- leave the asset type blank, which is reported honestly as its own
-- (unspecified) bucket rather than hidden.
CREATE TABLE counts_by_asset_type AS
SELECT
  asset_type,
  COUNT(*) AS projects
FROM cap_clean
GROUP BY asset_type;

-- Question C: rank the normalized categories by record count. category_rank 1
-- is the largest category over the whole window. pct_of_total is the category's
-- share of all project records, to one decimal.
CREATE TABLE category_ranking AS
WITH c AS (
  SELECT category_norm, COUNT(*) AS projects
  FROM cap_clean
  GROUP BY category_norm
),
t AS (SELECT SUM(projects) AS total FROM c)
SELECT
  DENSE_RANK() OVER (ORDER BY c.projects DESC) AS category_rank,
  c.category_norm,
  c.projects,
  round(100.0 * c.projects / t.total, 1) AS pct_of_total
FROM c CROSS JOIN t;

-- Question D (headline): the two ready-to-print lines run.py echoes. The total
-- record count with the category and year span, then the single largest
-- category, both read from the ranking.
CREATE TABLE headline AS
WITH r AS (SELECT * FROM category_ranking),
tot AS (SELECT SUM(projects) AS total, COUNT(*) AS cats FROM r),
yr AS (SELECT MIN(year) AS y0, MAX(year) AS y1 FROM cap_clean)
SELECT
  1 AS ord,
  'HRM records ' || (SELECT total FROM tot) || ' capital projects across '
    || (SELECT cats FROM tot) || ' categories and the years '
    || (SELECT y0 FROM yr) || ' to ' || (SELECT y1 FROM yr) || '.' AS line
UNION ALL
SELECT
  2 AS ord,
  'Largest category: ' || category_norm || ' with ' || projects
    || ' projects (' || pct_of_total || '% of the total).' AS line
FROM r
WHERE category_rank = 1
ORDER BY ord;
