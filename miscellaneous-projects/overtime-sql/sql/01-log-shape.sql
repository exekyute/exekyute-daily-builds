-- The shift log at a glance: how many shifts and employees, when the first
-- shift starts and the last one ends, how many weeks the log runs across,
-- and the shifts that make overtime hard to count. A week starts at 00:00 on
-- Sunday: date(starts, '-6 days', 'weekday 0') steps back six days and then
-- forward to a Sunday, staying put if it is already on one, which lands on
-- the Sunday on or before the start. A shift runs overnight when its last
-- minute falls on a later day than its first, so one that ends at exactly
-- 00:00 does not; it runs into the next week when it is still going at
-- 00:00 on the Sunday after it starts. A split day is an employee starting
-- two or more shifts on the same date. The weeks run from the week of the
-- first start to the week holding the last minute worked, so a log whose
-- last shift ends at exactly 00:00 on a Sunday does not reach the week that
-- starts then.
WITH timed AS (
    SELECT
        starts,
        ends,
        employee,
        CAST(strftime('%s', starts) AS INTEGER) / 60 AS start_min,
        CAST(strftime('%s', ends) AS INTEGER) / 60 AS end_min,
        CAST(strftime('%s', date(starts, '-6 days', 'weekday 0'), '+7 days') AS INTEGER) / 60 AS next_week_min
    FROM shifts
)
SELECT
    COUNT(*) AS shifts,
    COUNT(DISTINCT employee) AS employees,
    MIN(starts) AS first_start,
    MAX(ends) AS last_end,
    CAST((julianday(date(MAX(ends), '-1 minutes', '-6 days', 'weekday 0'))
          - julianday(date(MIN(starts), '-6 days', 'weekday 0'))) / 7 AS INTEGER) + 1 AS weeks,
    SUM(date(ends, '-1 minutes') > date(starts)) AS overnight,
    SUM(end_min > next_week_min) AS into_next_week,
    (SELECT COUNT(*) FROM (SELECT 1 FROM shifts GROUP BY employee, date(starts) HAVING COUNT(*) > 1))
        AS split_days,
    printf('%d:%02d', SUM(end_min - start_min) / 60, SUM(end_min - start_min) % 60) AS worked
FROM timed;
