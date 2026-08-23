-- Number each visitor's sessions. A running SUM over the starts_session flags
-- turns them into session ids: every new-session row bumps the count, every
-- other row inherits it. This flag-then-running-sum move is the whole trick.
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
)
SELECT visitor_id,
       SUM(starts_session) OVER (
           PARTITION BY visitor_id ORDER BY view_ts
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ) AS session_number,
       view_ts,
       page
FROM flags
ORDER BY visitor_id, view_ts;
