-- 99_export.sql
-- Question this step answers: what are the final, deterministic result files?
-- Write the two golden results and the frozen BI mart. Every query ends in an
-- ORDER BY so each file is byte-for-byte reproducible against expected/.

-- Meta: the literal pull-date constant and the latest full year it implies.
-- The browser dashboard reads this to pick the headline year, so the page and
-- the SQL headline agree by construction rather than by a second hardcoded date.
COPY (
  SELECT
    year(DATE '2026-07-09') - 1 AS latest_full_year,
    DATE '2026-07-09'           AS pull_date
) TO 'out/meta.csv' (HEADER, DELIMITER ',');

-- Golden 1: per-year counts and factor shares, oldest year first.
COPY (
  SELECT *
  FROM collisions_by_year
  ORDER BY year
) TO 'out/collisions_by_year.csv' (HEADER, DELIMITER ',');

-- Golden 2: the month-by-hour count matrix, hour 0 to 23 down the rows.
COPY (
  SELECT *
  FROM collisions_month_hour
  ORDER BY hour
) TO 'out/collisions_month_hour.csv' (HEADER, DELIMITER ',');

-- BI mart: one wide, denormalized row per collision for Tableau and Power BI.
-- The factor flags keep their source-style uppercase names so the Power BI DAX
-- in bi/README.md binds to them verbatim. Ordered by collision_id so the frozen
-- export never reshuffles between runs.
COPY (
  SELECT
    collision_id,
    accident_date,
    year,
    month,
    hour,
    weekday,
    lat,
    lon,
    road_location_1,
    road_location_2,
    collision_configuration,
    light_condition,
    weather_condition,
    PEDESTRIAN_COLLISIONS,
    BICYCLE_COLLISIONS,
    IMPAIRED_DRIVING,
    DISTRACTED_DRIVING,
    AGRESSIVE_DRIVING,
    INTERSECTION_RELATED,
    FATAL_INJURY,
    NON_FATAL_INJURY
  FROM collisions_clean
  ORDER BY collision_id
) TO 'out/mart_collisions.csv' (HEADER, DELIMITER ',');
