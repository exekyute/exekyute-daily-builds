-- Members with no visit in 14 or more days as of the report date, plus members
-- who joined but never checked in at all. The LEFT JOIN is what keeps the
-- never-visited members in the result.
WITH params AS (
    SELECT DATE('2026-08-19') AS as_of
),
last_visit AS (
    SELECT member_id, MAX(DATE(checkin_ts)) AS last_day
    FROM checkins
    GROUP BY member_id
)
SELECT m.name,
       m.joined_date,
       lv.last_day,
       CAST(julianday(p.as_of) - julianday(lv.last_day) AS INTEGER) AS days_since
FROM members m
LEFT JOIN last_visit lv USING (member_id)
CROSS JOIN params p
WHERE lv.last_day IS NULL
   OR julianday(p.as_of) - julianday(lv.last_day) >= 14
ORDER BY (lv.last_day IS NULL) DESC, days_since DESC;
