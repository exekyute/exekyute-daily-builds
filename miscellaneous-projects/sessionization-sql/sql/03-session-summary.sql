-- One row per session: when it ran, how long, how many pages, and the entry
-- and exit pages. LAST_VALUE needs the full-partition frame spelled out;
-- its default frame stops at the current row and would return each row's own
-- page instead of the session's last one.
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
    SELECT visitor_id, view_ts, page,
           CASE WHEN gap_seconds IS NULL OR gap_seconds >= 1800 THEN 1 ELSE 0 END AS starts_session
    FROM ordered
),
numbered AS (
    SELECT visitor_id, view_ts, page,
           SUM(starts_session) OVER (
               PARTITION BY visitor_id ORDER BY view_ts
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
           ) AS session_number
    FROM flags
),
detailed AS (
    SELECT visitor_id, session_number, view_ts, page,
           FIRST_VALUE(page) OVER (
               PARTITION BY visitor_id, session_number ORDER BY view_ts
           ) AS entry_page,
           LAST_VALUE(page) OVER (
               PARTITION BY visitor_id, session_number ORDER BY view_ts
               ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
           ) AS exit_page
    FROM numbered
)
SELECT visitor_id,
       session_number,
       MIN(view_ts) AS started,
       MAX(view_ts) AS ended,
       ROUND((CAST(strftime('%s', MAX(view_ts)) AS INTEGER)
            - CAST(strftime('%s', MIN(view_ts)) AS INTEGER)) / 60.0, 2) AS minutes,
       COUNT(*) AS pages,
       entry_page,
       exit_page
FROM detailed
GROUP BY visitor_id, session_number, entry_page, exit_page
ORDER BY visitor_id, session_number;
