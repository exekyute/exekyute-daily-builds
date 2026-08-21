-- Streaks still alive on the report date: islands whose last day is the as-of date.
-- The as-of date is pinned so the sample data gives the same answer every run.
-- Swap it for DATE('now') against live data.
WITH params AS (
    SELECT DATE('2026-08-19') AS as_of
),
days AS (
    SELECT DISTINCT member_id, DATE(checkin_ts) AS day
    FROM checkins
),
numbered AS (
    SELECT member_id, day,
           ROW_NUMBER() OVER (PARTITION BY member_id ORDER BY day) AS rn
    FROM days
),
islands AS (
    SELECT member_id,
           DATE(day, '-' || rn || ' days') AS island_key,
           MIN(day)  AS streak_start,
           MAX(day)  AS streak_end,
           COUNT(*)  AS streak_days
    FROM numbered
    GROUP BY member_id, island_key
)
SELECT m.name, i.streak_start, i.streak_days
FROM islands i
JOIN members m USING (member_id)
CROSS JOIN params p
WHERE i.streak_end = p.as_of
ORDER BY i.streak_days DESC, m.name;
