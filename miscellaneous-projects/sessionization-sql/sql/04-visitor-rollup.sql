-- Per-visitor totals across their sessions. A bounce is a one-page session;
-- SUM(pages = 1) counts them because the comparison is 1 when true and 0 when
-- not, the same flag-summing move the session ids use.
WITH ordered AS (
    SELECT visitor_id,
           view_ts,
           page,
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
SELECT visitor_id,
       COUNT(*) AS sessions,
       SUM(pages) AS views,
       SUM(pages = 1) AS bounces,
       ROUND(1.0 * SUM(pages) / COUNT(*), 2) AS pages_per_session,
       ROUND(SUM(minutes), 2) AS total_minutes
FROM summary
GROUP BY visitor_id
ORDER BY visitor_id;
