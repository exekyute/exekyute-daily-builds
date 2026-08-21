-- Visit summary per member. Timestamps collapse to distinct calendar days first,
-- so two check-ins on the same day count as one visit.
WITH days AS (
    SELECT DISTINCT member_id, DATE(checkin_ts) AS day
    FROM checkins
)
SELECT m.name,
       COUNT(d.day)  AS days_visited,
       MIN(d.day)    AS first_visit,
       MAX(d.day)    AS last_visit
FROM members m
LEFT JOIN days d USING (member_id)
GROUP BY m.member_id
ORDER BY m.name;
