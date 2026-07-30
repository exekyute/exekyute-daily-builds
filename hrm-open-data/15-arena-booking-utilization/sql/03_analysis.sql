-- 03_analysis.sql
-- The analytical core. One long mart at the use-type grain (the frozen BI file), one
-- wide table at the facility-month grain (the golden), and a three-line headline.
-- Every hours figure is rounded to three decimals; every rate to four. Both rate
-- denominators are guarded so a zero can never divide (the snapshot has none, so the
-- guards never fire).

-- Table A (BI mart): one row per facility, month, and use type. This is the file both
-- dashboards read. bookings is the row count of bookings that fell in the group and
-- booked_hours is their summed duration. The three use-type rows of a facility-month
-- partition its total, so summing booked_hours back over use types returns the
-- facility-month total with no double counting.
CREATE TABLE mart_use AS
SELECT
  facility,
  month_start,
  year,
  use_type,
  COUNT(*)                    AS bookings,
  round(SUM(booked_hours), 3) AS booked_hours
FROM ab_clean
GROUP BY facility, month_start, year, use_type;

-- Table B (golden): one row per facility and month, carrying the booked-hours total,
-- the ice / dry-floor / other split as three columns, the ice share of the total, and
-- the utilization proxy. days_in_month is the calendar length of the month;
-- capacity_hours is that length times the documented OPEN_HOURS_PER_DAY constant held
-- in params; utilization is the month's booked hours over that nominal capacity. The
-- proxy is a booking-intensity measure, not a true occupancy rate: because separate
-- bookings on one pad can overlap (a full-day system hold sits under real ice time)
-- and OPEN_HOURS_PER_DAY is fixed, utilization can exceed 1.0. See data_dictionary.md.
CREATE TABLE facility_month AS
WITH agg AS (
  SELECT
    facility,
    month_start,
    year,
    COUNT(*)          AS bookings,
    SUM(booked_hours) AS booked_hours,
    SUM(CASE WHEN use_type = 'Ice'       THEN booked_hours ELSE 0 END) AS ice_hours,
    SUM(CASE WHEN use_type = 'Dry Floor' THEN booked_hours ELSE 0 END) AS dry_floor_hours,
    SUM(CASE WHEN use_type = 'Other'     THEN booked_hours ELSE 0 END) AS other_hours
  FROM ab_clean
  GROUP BY facility, month_start, year
)
SELECT
  a.facility,
  a.month_start,
  a.year,
  a.bookings,
  round(a.booked_hours, 3)                                            AS booked_hours,
  round(a.ice_hours, 3)                                              AS ice_hours,
  round(a.dry_floor_hours, 3)                                        AS dry_floor_hours,
  round(a.other_hours, 3)                                            AS other_hours,
  CASE WHEN a.booked_hours = 0 THEN NULL
       ELSE round(a.ice_hours / a.booked_hours, 4) END               AS ice_share,
  day(last_day(a.month_start))                                       AS days_in_month,
  day(last_day(a.month_start)) * p.open_hours_per_day                AS capacity_hours,
  CASE WHEN day(last_day(a.month_start)) * p.open_hours_per_day = 0 THEN NULL
       ELSE round(a.booked_hours / (day(last_day(a.month_start)) * p.open_hours_per_day), 4)
  END                                                                AS utilization
FROM agg a
CROSS JOIN params p;

-- Table C (headline): three ready-to-print lines. The total booked hours, the ice
-- share of hours with the dry-floor and other shares alongside, and the busiest
-- facility by booked hours. run.py prints these lines; it does not compute them.
CREATE TABLE headline AS
WITH tot AS (
  SELECT
    SUM(booked_hours)                                                 AS total_hours,
    SUM(CASE WHEN use_type = 'Ice'       THEN booked_hours ELSE 0 END) AS ice_hours,
    SUM(CASE WHEN use_type = 'Dry Floor' THEN booked_hours ELSE 0 END) AS dry_hours,
    SUM(CASE WHEN use_type = 'Other'     THEN booked_hours ELSE 0 END) AS other_hours,
    COUNT(DISTINCT facility)                                          AS n_facilities,
    COUNT(DISTINCT month_start)                                       AS n_months
  FROM ab_clean
),
busiest AS (
  SELECT facility, SUM(booked_hours) AS fac_hours
  FROM ab_clean
  GROUP BY facility
  ORDER BY fac_hours DESC, facility
  LIMIT 1
)
SELECT 1 AS ord,
  'Total booked arena hours: ' || printf('%.2f', (SELECT total_hours FROM tot))
    || ' across ' || (SELECT n_facilities FROM tot) || ' facilities and '
    || (SELECT n_months FROM tot) || ' months.' AS line
UNION ALL
SELECT 2 AS ord,
  'Ice is ' || printf('%.2f', 100.0 * (SELECT ice_hours FROM tot) / (SELECT total_hours FROM tot))
    || ' percent of booked hours (' || printf('%.2f', (SELECT ice_hours FROM tot))
    || ' of ' || printf('%.2f', (SELECT total_hours FROM tot)) || '); dry floor '
    || printf('%.2f', 100.0 * (SELECT dry_hours FROM tot) / (SELECT total_hours FROM tot))
    || ' percent, other '
    || printf('%.2f', 100.0 * (SELECT other_hours FROM tot) / (SELECT total_hours FROM tot))
    || ' percent.' AS line
UNION ALL
SELECT 3 AS ord,
  'Busiest facility: ' || (SELECT facility FROM busiest) || ' with '
    || printf('%.2f', (SELECT fac_hours FROM busiest)) || ' booked hours.' AS line
ORDER BY ord;
