-- 99_export.sql
-- Question this step answers: what are the final, deterministic output files?
-- Two writes. The golden facility-month table goes to out/ for the row-for-row
-- verify; the frozen use-type mart goes to bi/exports/ for both BI faces to read.
-- Every COPY ends in an ORDER BY so the row order is stable and the files diff byte
-- for byte.

-- Golden: one row per facility and month, ordered by facility then month so a
-- facility's calendar reads top to bottom. Carries the booked-hours total, the ice /
-- dry-floor / other split, the ice share, and the utilization proxy with the days and
-- capacity it is built from.
COPY (
  SELECT
    facility,
    month_start,
    year,
    bookings,
    booked_hours,
    ice_hours,
    dry_floor_hours,
    other_hours,
    ice_share,
    days_in_month,
    capacity_hours,
    utilization
  FROM facility_month
  ORDER BY facility, month_start
) TO 'out/arena_utilization.csv' (HEADER, DELIMITER ',');

-- Frozen mart: one row per facility, month, and use type. This is the file both
-- dashboards bind to. Ordered by facility, month, then use type for a stable
-- snapshot. Summing booked_hours over every row returns the total the numbers-match
-- line asserts; filtering to use_type = 'Ice' returns the ice hours.
COPY (
  SELECT
    facility,
    month_start,
    year,
    use_type,
    bookings,
    booked_hours
  FROM mart_use
  ORDER BY facility, month_start, use_type
) TO 'bi/exports/mart_arena.csv' (HEADER, DELIMITER ',');
