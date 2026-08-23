-- Each page view with the time since that visitor's previous view and a flag
-- for whether it starts a new session. A gap of 30 minutes or more starts one,
-- and so does a visitor's first view. Gaps are compared in whole seconds via
-- strftime('%s') because julianday() differences are floats, and a gap of
-- exactly 30 minutes could land a hair under the threshold.
WITH ordered AS (
    SELECT visitor_id,
           view_ts,
           page,
           CAST(strftime('%s', view_ts) AS INTEGER)
             - CAST(strftime('%s', LAG(view_ts) OVER (
                   PARTITION BY visitor_id ORDER BY view_ts
               )) AS INTEGER) AS gap_seconds
    FROM pageviews
)
SELECT visitor_id,
       view_ts,
       page,
       gap_seconds,
       CASE WHEN gap_seconds IS NULL OR gap_seconds >= 1800 THEN 1 ELSE 0 END AS starts_session
FROM ordered
ORDER BY visitor_id, view_ts;
