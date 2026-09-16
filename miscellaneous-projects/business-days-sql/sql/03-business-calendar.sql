-- The calendar the counting rests on, built the same way in queries 04 and
-- 05. A recursive CTE walks one day at a time from the first ticket to
-- thirty days past the last one, or to the last answer if that falls
-- further out, far enough that every due date it has to name is on it. Each day is open
-- unless it falls on a weekend or in the holidays table, and a running SUM
-- over the open days numbers them: business_no is how many days the desk
-- has been open up to and including this one.
--
-- A closed day keeps the number of the open day before it, so the count
-- stands still over a weekend and starts again on Monday. That numbering
-- turns both questions the desk asks into arithmetic: business days
-- between two dates is one number minus the other, and three business days
-- after a date is the day whose number is three higher.
WITH RECURSIVE bounds AS (
    SELECT MIN(opened_on) AS first_day,
           MAX(DATE(MAX(opened_on), '+30 days'), COALESCE(MAX(responded_on), '')) AS last_day
    FROM tickets
),
days(day) AS (
    SELECT first_day FROM bounds
    UNION ALL
    SELECT DATE(d.day, '+1 day') FROM days d, bounds b WHERE d.day < b.last_day
),
calendar AS (
    SELECT d.day,
           CASE WHEN strftime('%w', d.day) IN ('0', '6') THEN 0
                WHEN EXISTS (SELECT 1 FROM holidays h WHERE h.holiday_on = d.day) THEN 0
                ELSE 1 END AS is_business
    FROM days d
)
SELECT day,
       CASE strftime('%w', day)
            WHEN '0' THEN 'Sun' WHEN '1' THEN 'Mon' WHEN '2' THEN 'Tue' WHEN '3' THEN 'Wed'
            WHEN '4' THEN 'Thu' WHEN '5' THEN 'Fri' ELSE 'Sat' END AS weekday,
       CASE WHEN is_business = 1 THEN 'open'
            ELSE COALESCE((SELECT h.name FROM holidays h WHERE h.holiday_on = day), 'weekend') END AS desk,
       SUM(is_business) OVER (ORDER BY day ROWS UNBOUNDED PRECEDING) AS business_no
FROM calendar
ORDER BY day;
