-- The same three-day target counted in business days. Every ticket is
-- joined to the calendar on the day it was opened and on the day it was
-- answered, and the difference between the two business numbers is how
-- many days the desk was open in between. The due date is found the same
-- way, by joining back to the open day whose number is three higher.
--
-- A ticket answered the day it arrived comes to 0, and one still waiting
-- has no responded_on to join to, so its age is blank and its verdict is
-- open. The calendar runs past the last ticket, so a due date after the
-- last answer still has a day to name.
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
),
numbered AS (
    SELECT day, is_business,
           SUM(is_business) OVER (ORDER BY day ROWS UNBOUNDED PRECEDING) AS business_no
    FROM calendar
)
SELECT t.ticket_id,
       t.opened_on,
       due.day AS due_on,
       t.responded_on,
       answered.business_no - opened.business_no AS business_days,
       CASE WHEN t.responded_on IS NULL THEN 'open'
            WHEN answered.business_no - opened.business_no <= 3 THEN 'met'
            ELSE 'missed' END AS verdict
FROM tickets t
JOIN numbered opened ON opened.day = t.opened_on
JOIN numbered due ON due.is_business = 1 AND due.business_no = opened.business_no + 3
LEFT JOIN numbered answered ON answered.day = t.responded_on
ORDER BY t.ticket_id;
