-- The rule the desk actually works to: a ticket that arrives on a closed
-- day starts its clock on the next day the desk is open. In the numbering
-- that is one line of arithmetic. A closed day carries the number of the
-- open day before it, so adding 1 on a closed day and 0 on an open one
-- gives the number of the day the work can start.
--
-- The clock_moved column marks the tickets this changes. Their due dates
-- move out by one business day, and a ticket answered on what query 04
-- called the fourth business day can come back inside the target. An
-- answer logged on a closed day before the clock starts, the day the
-- ticket arrived or any closed day after it, would otherwise count as a
-- day below zero, so the age is floored at 0. The verdict reads the raw
-- difference, which -1 and 0 both meet.
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
       started.day AS starts_on,
       CASE WHEN started.day <> t.opened_on THEN 'yes' ELSE '' END AS clock_moved,
       due.day AS due_on,
       t.responded_on,
       MAX(answered.business_no - started.business_no, 0) AS business_days,
       CASE WHEN t.responded_on IS NULL THEN 'open'
            WHEN answered.business_no - started.business_no <= 3 THEN 'met'
            ELSE 'missed' END AS verdict
FROM tickets t
JOIN numbered opened ON opened.day = t.opened_on
JOIN numbered started ON started.is_business = 1
                     AND started.business_no = opened.business_no + (1 - opened.is_business)
JOIN numbered due ON due.is_business = 1 AND due.business_no = started.business_no + 3
LEFT JOIN numbered answered ON answered.day = t.responded_on
ORDER BY t.ticket_id;
