-- 03_analysis.sql
-- The analytical core. Every rollup below reads permit_mart and restricts to
-- permits that carry an issuance date (issue_year IS NOT NULL), because a permit
-- with no issuance date cannot be placed in a year. Permits without a year still
-- live in permit_mart and in the exported per-permit mart; they are only left out
-- of the year-based rollups.

-- Table A (golden): permit activity and declared value by issue year and work
-- type. One row per year and work type: how many permits, the total declared
-- project value to the cent, and the total net new residential units. A missing
-- estimated value is treated as zero for the money sum; net_new_units is never
-- null in the snapshot.
CREATE TABLE permits_by_year_worktype AS
SELECT
  issue_year,
  work_type,
  COUNT(*)                                    AS permit_count,
  ROUND(SUM(COALESCE(project_value, 0)), 2)   AS total_project_value,
  SUM(net_new_units)                          AS total_net_new_units
FROM permit_mart
WHERE issue_year IS NOT NULL
GROUP BY issue_year, work_type;

-- Table B (golden): where net new residential units are landing, as a per-district
-- running total. First sum net new units per district and year, then carry a
-- cumulative sum across years within each district. The window is partitioned by
-- district and ordered by year, which is exactly the running-total table
-- calculation the Tableau guide rebuilds (Compute Using issue_year, partition by
-- district).
CREATE TABLE district_units_running_total AS
WITH district_year AS (
  SELECT
    district,
    issue_year,
    SUM(net_new_units) AS net_new_units
  FROM permit_mart
  WHERE issue_year IS NOT NULL
  GROUP BY district, issue_year
)
SELECT
  district,
  issue_year,
  net_new_units,
  SUM(net_new_units) OVER (
    PARTITION BY district
    ORDER BY issue_year
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS cumulative_net_new_units
FROM district_year;

-- Table C (dashboard feed, not a golden): declared value and units by community
-- over all issued permits, so the browser dashboard can rank communities. The
-- money total across communities equals the money total across year-and-work-type
-- rows, which is what lets the dashboard reconcile to the golden.
CREATE TABLE permits_by_community AS
SELECT
  CASE WHEN community IS NULL OR community = '' THEN '(Unspecified)' ELSE community END
                                              AS community,
  COUNT(*)                                    AS permit_count,
  ROUND(SUM(COALESCE(project_value, 0)), 2)   AS total_project_value,
  SUM(net_new_units)                          AS total_net_new_units
FROM permit_mart
WHERE issue_year IS NOT NULL
GROUP BY 1;

-- Headline: two ready-to-read lines for the console. run.py prints these; it does
-- not compute them. Line one is the numbers-match anchor carried into both BI
-- guides: the total declared project value for the latest full issue year.
CREATE TABLE headline AS
WITH latest AS (
  SELECT
    p.latest_full_year                          AS year,
    SUM(r.permit_count)                         AS permits,
    ROUND(SUM(r.total_project_value), 2)        AS value
  FROM permits_by_year_worktype r
  CROSS JOIN params p
  WHERE r.issue_year = p.latest_full_year
  GROUP BY p.latest_full_year
),
overall AS (
  SELECT
    MIN(issue_year)                             AS year_first,
    MAX(issue_year)                             AS year_last,
    SUM(permit_count)                           AS permits,
    ROUND(SUM(total_project_value), 2)          AS value,
    SUM(total_net_new_units)                    AS units
  FROM permits_by_year_worktype
)
SELECT 1 AS ord,
  printf('Total declared project value for issue year %d: $%.2f across %d permits.',
         latest.year, latest.value, latest.permits) AS line
FROM latest
UNION ALL
SELECT 2 AS ord,
  printf('All issued permits %d to %d: %d permits, $%.2f declared, %d net new units.',
         overall.year_first, overall.year_last, overall.permits, overall.value, overall.units) AS line
FROM overall
ORDER BY ord;
