-- Every consecutive-day streak per member: the gaps-and-islands pattern.
-- Subtracting each day's row number from the day itself gives a key that is
-- constant across consecutive days and jumps whenever a day is skipped.
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
    SELECT member_id, day,
           DATE(day, '-' || rn || ' days') AS island_key
    FROM numbered
)
SELECT m.name,
       MIN(i.day)  AS streak_start,
       MAX(i.day)  AS streak_end,
       COUNT(*)    AS streak_days
FROM islands i
JOIN members m USING (member_id)
GROUP BY i.member_id, i.island_key
ORDER BY m.name, streak_start;
