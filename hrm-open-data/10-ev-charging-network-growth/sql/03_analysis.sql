-- 03_analysis.sql
-- Three questions plus a headline. The grain is one row per charger, so every
-- measure here is a count of charger records, never a sum of ports. One record
-- is one installed public charging station.

-- Question A: how many chargers were installed in each year, and what is the
-- running cumulative network size through that year? cumulative_chargers is a
-- windowed running total over the ordered years, so it reads 10 by 2024, then
-- 29, then 33: the growth curve the Tableau running-total area and the Power BI
-- cumulative measure both draw.
CREATE TABLE chargers_by_year AS
WITH per_year AS (
  SELECT install_year, COUNT(*) AS chargers
  FROM ev_clean
  GROUP BY install_year
)
SELECT
  install_year,
  chargers,
  SUM(chargers) OVER (
    ORDER BY install_year
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS cumulative_chargers
FROM per_year;

-- Question B: how many chargers carry each charging level? L2 is Level 2 (slow
-- AC); DCFC is a DC fast charger. This is the first of the two breakdowns that
-- carry the second dimension alongside the short growth curve.
CREATE TABLE counts_by_chartype AS
SELECT
  chartype,
  COUNT(*) AS chargers
FROM ev_clean
GROUP BY chartype;

-- Question C: how many chargers carry each connector type? J1772 is the Level 2
-- connector; the CCS-family connectors sit on the DC fast chargers.
CREATE TABLE counts_by_connectype AS
SELECT
  connectype,
  COUNT(*) AS chargers
FROM ev_clean
GROUP BY connectype;

-- Question D (headline): the three ready-to-print lines run.py echoes. The total
-- network size with the install-year span, then the cumulative curve read off
-- chargers_by_year, then the two mix breakdowns. Every figure is read from the
-- tables above, not hardcoded.
CREATE TABLE headline AS
WITH tot AS (
  SELECT COUNT(*) AS chargers, MIN(install_year) AS y0, MAX(install_year) AS y1
  FROM ev_clean
),
curve AS (
  SELECT string_agg(cumulative_chargers || ' by ' || install_year, ', ' ORDER BY install_year) AS s
  FROM chargers_by_year
),
levels AS (
  SELECT string_agg(chargers || ' ' || chartype, ', ' ORDER BY chargers DESC, chartype) AS s
  FROM counts_by_chartype
),
conns AS (
  SELECT string_agg(chargers || ' ' || connectype, ', ' ORDER BY chargers DESC, connectype) AS s
  FROM counts_by_connectype
)
SELECT 1 AS ord,
  'HRM lists ' || (SELECT chargers FROM tot)
    || ' public EV charging stations, every one HRM-owned and publicly '
    || 'accessible, installed across ' || (SELECT y0 FROM tot) || ' to '
    || (SELECT y1 FROM tot) || '.' AS line
UNION ALL
SELECT 2 AS ord,
  'The network grew cumulatively to ' || (SELECT s FROM curve) || '.' AS line
UNION ALL
SELECT 3 AS ord,
  'By charging level: ' || (SELECT s FROM levels)
    || '. By connector: ' || (SELECT s FROM conns) || '.' AS line
ORDER BY ord;
