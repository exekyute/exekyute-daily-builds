-- The clock most people write first: three days on the wall calendar. The
-- due date is the opening date plus three days, and the age of a ticket is
-- the difference between two julianday numbers, which counts every day the
-- same whether the desk was open or not.
--
-- The desk_on_due column says whether the due date it works out is a day
-- the desk is even open. A target that falls on a Sunday or a holiday is
-- not a target anyone can meet.
SELECT t.ticket_id,
       t.opened_on,
       DATE(t.opened_on, '+3 days') AS due_on,
       CASE WHEN strftime('%w', DATE(t.opened_on, '+3 days')) IN ('0', '6') THEN 'closed, weekend'
            WHEN EXISTS (SELECT 1 FROM holidays h WHERE h.holiday_on = DATE(t.opened_on, '+3 days'))
              THEN 'closed, holiday'
            ELSE 'open' END AS desk_on_due,
       t.responded_on,
       CAST(julianday(t.responded_on) - julianday(t.opened_on) AS INTEGER) AS calendar_days,
       CASE WHEN t.responded_on IS NULL THEN 'open'
            WHEN julianday(t.responded_on) - julianday(t.opened_on) <= 3 THEN 'met'
            ELSE 'missed' END AS verdict
FROM tickets t
ORDER BY t.ticket_id;
