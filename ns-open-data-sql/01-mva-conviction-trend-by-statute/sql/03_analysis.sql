-- 03_analysis.sql
-- The analytical core. Three questions, three tables.

-- Question A: for each offence, what were its first-year and last-year counts,
-- and did it rise or fall across the whole window?
-- arg_min / arg_max pick the convictions value at the earliest and latest year.
CREATE TABLE offence_window AS
SELECT
  offence_statute,
  description,
  MIN(year_convicted)                  AS first_year,
  MAX(year_convicted)                  AS last_year,
  arg_min(convictions, year_convicted) AS first_convictions,
  arg_max(convictions, year_convicted) AS last_convictions
FROM mva_yearly
GROUP BY offence_statute, description;

-- Question B: ranked across offences, which is the fastest rising and which is
-- the fastest falling over the window?
-- window_pct_change is the net first-to-last change as a percent, which is
-- comparable across offences of very different volume. window_rank = 1 is the
-- steepest riser; the largest window_rank is the steepest faller.
CREATE TABLE offence_window_ranked AS
WITH w AS (
  SELECT
    *,
    last_convictions - first_convictions AS window_change,
    round(100.0 * (last_convictions - first_convictions) / first_convictions, 1)
      AS window_pct_change
  FROM offence_window
)
SELECT
  *,
  CASE
    WHEN window_change > 0 THEN 'rising'
    WHEN window_change < 0 THEN 'falling'
    ELSE 'flat'
  END AS window_trend,
  DENSE_RANK() OVER (ORDER BY window_pct_change DESC) AS window_rank
FROM w;

-- Question C: within each year, how do the offences rank by count, and how did
-- each offence change from the prior year?
-- rank_in_year ranks offences by convictions inside each year. prev_convictions
-- uses LAG over the offence's own year sequence, which drives the year-over-year
-- change and percent. The first observed year has no prior, so those stay NULL.
CREATE TABLE convictions_ranked AS
WITH detail AS (
  SELECT
    offence_statute,
    description,
    year_convicted,
    convictions,
    DENSE_RANK() OVER (PARTITION BY year_convicted ORDER BY convictions DESC)
      AS rank_in_year,
    LAG(convictions) OVER (PARTITION BY offence_statute ORDER BY year_convicted)
      AS prev_convictions
  FROM mva_yearly
)
SELECT
  ow.window_rank,
  ow.window_trend,
  d.offence_statute,
  d.description,
  d.year_convicted,
  d.convictions,
  d.rank_in_year,
  d.prev_convictions,
  d.convictions - d.prev_convictions AS yoy_change,
  round(100.0 * (d.convictions - d.prev_convictions) / d.prev_convictions, 1)
    AS yoy_pct_change,
  ow.first_year,
  ow.last_year,
  ow.first_convictions,
  ow.last_convictions,
  ow.window_change,
  ow.window_pct_change
FROM detail d
JOIN offence_window_ranked ow USING (offence_statute, description);

-- Question D (headline): name the single fastest-rising and fastest-falling
-- offence over the window, as two ready-to-read lines for the console.
CREATE TABLE headline AS
WITH ranked AS (SELECT * FROM offence_window_ranked)
SELECT
  1 AS ord,
  'Fastest rising:  ' || description || ' (' || offence_statute || '), '
    || first_convictions || ' in ' || first_year || ' to '
    || last_convictions || ' in ' || last_year
    || ' (' || CASE WHEN window_pct_change >= 0 THEN '+' ELSE '' END
    || window_pct_change || '%).' AS line
FROM ranked
WHERE window_rank = (SELECT MIN(window_rank) FROM ranked)
UNION ALL
SELECT
  2 AS ord,
  'Fastest falling: ' || description || ' (' || offence_statute || '), '
    || first_convictions || ' in ' || first_year || ' to '
    || last_convictions || ' in ' || last_year
    || ' (' || CASE WHEN window_pct_change >= 0 THEN '+' ELSE '' END
    || window_pct_change || '%).' AS line
FROM ranked
WHERE window_rank = (SELECT MAX(window_rank) FROM ranked)
ORDER BY ord;
