-- SLA and aging queries.
--
-- Days are whole-day counts from julianday differences. Both dates sit at midnight,
-- so the difference is a whole number of days. A request breaches its SLA when its
-- days to close is strictly greater than the category target, so closing exactly on
-- the target day is on time.

-- name: time_to_close
-- For each category, over the requests that are closed: how many were closed, the
-- total days they took (so an exact average can be formed), the target, and how many
-- breached the target.
SELECT
    t.category,
    t.target_days,
    COUNT(*) AS closed_count,
    SUM(c.days_to_close) AS total_days,
    SUM(CASE WHEN c.days_to_close > t.target_days THEN 1 ELSE 0 END) AS breaches
FROM (
    SELECT
        category,
        CAST(julianday(closed_date) - julianday(opened_date) AS INTEGER) AS days_to_close
    FROM clean_requests
    WHERE closed_date IS NOT NULL
) c
JOIN sla_targets t ON t.category = c.category
GROUP BY t.category
ORDER BY t.category;

-- name: open_aging
-- For the requests still open as of the report date: how many fall in each age
-- bucket, and how many in each bucket are past their category target.
WITH open_days AS (
    SELECT
        CAST(julianday(:as_of) - julianday(c.opened_date) AS INTEGER) AS days_open,
        t.target_days
    FROM clean_requests c
    JOIN sla_targets t ON t.category = c.category
    WHERE c.closed_date IS NULL
)
SELECT
    CASE
        WHEN days_open <= 7  THEN '0-7'
        WHEN days_open <= 14 THEN '8-14'
        WHEN days_open <= 30 THEN '15-30'
        ELSE '31+'
    END AS bucket,
    COUNT(*) AS open_count,
    SUM(CASE WHEN days_open > target_days THEN 1 ELSE 0 END) AS overdue
FROM open_days
GROUP BY bucket
ORDER BY MIN(days_open);
