-- The two frames side by side, grouped by how many calendar days the ROWS
-- frame reached across. Both averages here are the same sum over the rows
-- in the frame, so the difference between them, drift, comes from the frame
-- alone: the ROWS average less the RANGE one. Where the seven rows sit
-- inside seven days the two frames hold the same rows and agree. For each
-- span the report shows how many days reached it, on how many of them the
-- averages differ, and the day that differs most, the earliest if two tie,
-- with both averages for that day. Both frames are worked out in one pass,
-- and the day that differs most is picked with ROW_NUMBER rather than a
-- second look at the frames: SQLite before 3.35 works a CTE out again every
-- time it is named.
WITH numbered AS (
    SELECT day, sales_cents, CAST(julianday(day) AS INTEGER) AS day_no FROM daily_sales
),
framed AS (
    SELECT
        day,
        day_no - MIN(day_no) OVER last_seven_rows + 1 AS calendar_days,
        (2 * SUM(sales_cents) OVER last_seven_rows + COUNT(*) OVER last_seven_rows)
            / (2 * COUNT(*) OVER last_seven_rows) AS rows_avg,
        (2 * SUM(sales_cents) OVER seven_days + COUNT(*) OVER seven_days)
            / (2 * COUNT(*) OVER seven_days) AS range_avg
    FROM numbered
    WINDOW last_seven_rows AS (ORDER BY day_no ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
           seven_days AS (ORDER BY day_no RANGE BETWEEN 6 PRECEDING AND CURRENT ROW)
),
ranked AS (
    SELECT
        calendar_days,
        day,
        rows_avg,
        range_avg,
        rows_avg - range_avg AS drift,
        ROW_NUMBER() OVER (PARTITION BY calendar_days ORDER BY abs(rows_avg - range_avg) DESC, day) AS place
    FROM framed
)
SELECT
    calendar_days,
    COUNT(*) AS days,
    SUM(drift <> 0) AS days_differing,
    MAX(CASE WHEN place = 1 THEN CASE WHEN drift < 0 THEN '-' ELSE '' END
                                 || printf('%d.%02d', abs(drift) / 100, abs(drift) % 100) END) AS largest_drift,
    MAX(CASE WHEN place = 1 THEN day END) AS on_day,
    MAX(CASE WHEN place = 1 THEN printf('%d.%02d', rows_avg / 100, rows_avg % 100) END) AS rows_avg,
    MAX(CASE WHEN place = 1 THEN printf('%d.%02d', range_avg / 100, range_avg % 100) END) AS range_avg
FROM ranked
GROUP BY calendar_days
ORDER BY calendar_days;
