-- The whole site in one row: visitors, sessions, views, bounce rate, and the
-- averages. Everything derives from the same session summary the other
-- queries build, so the numbers always agree with them.
WITH ordered AS (
    SELECT visitor_id,
           view_ts,
           CAST(strftime('%s', view_ts) AS INTEGER)
             - CAST(strftime('%s', LAG(view_ts) OVER (
                   PARTITION BY visitor_id ORDER BY view_ts
               )) AS INTEGER) AS gap_seconds
    FROM pageviews
),
flags AS (
    SELECT visitor_id, view_ts,
           CASE WHEN gap_seconds IS NULL OR gap_seconds >= 1800 THEN 1 ELSE 0 END AS starts_session
    FROM ordered
),
numbered AS (
    SELECT visitor_id, view_ts,
           SUM(starts_session) OVER (
               PARTITION BY visitor_id ORDER BY view_ts
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
           ) AS session_number
    FROM flags
),
summary AS (
    SELECT visitor_id,
           session_number,
           ROUND((CAST(strftime('%s', MAX(view_ts)) AS INTEGER)
                - CAST(strftime('%s', MIN(view_ts)) AS INTEGER)) / 60.0, 2) AS minutes,
           COUNT(*) AS pages
    FROM numbered
    GROUP BY visitor_id, session_number
)
SELECT COUNT(DISTINCT visitor_id) AS visitors,
       COUNT(*) AS sessions,
       SUM(pages) AS views,
       SUM(pages = 1) AS bounces,
       printf('%.1f%%', 100.0 * SUM(pages = 1) / COUNT(*)) AS bounce_rate,
       ROUND(1.0 * SUM(pages) / COUNT(*), 2) AS avg_pages_per_session,
       ROUND(AVG(minutes), 2) AS avg_session_minutes
FROM summary;
