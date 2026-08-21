-- Longest streak per member: rank each member's islands by length and keep the top one.
-- Ties break on the earlier streak.
WITH days AS (
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
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY member_id
               ORDER BY streak_days DESC, streak_start
           ) AS pos
    FROM islands
)
SELECT m.name, r.streak_start, r.streak_end, r.streak_days
FROM ranked r
JOIN members m USING (member_id)
WHERE r.pos = 1
ORDER BY r.streak_days DESC, m.name;
