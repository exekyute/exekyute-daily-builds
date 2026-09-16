-- The log at a glance: how many tickets, how many are answered, the dates
-- they run between, and how many days the desk lists as closed. Dates are
-- held as YYYY-MM-DD text, which compares and sorts in date order, and a
-- ticket with no responded_on is still waiting, so COUNT on that column
-- counts the answered ones.
SELECT COUNT(*) AS tickets,
       COUNT(responded_on) AS answered,
       COUNT(*) - COUNT(responded_on) AS still_open,
       MIN(opened_on) AS first_opened,
       MAX(opened_on) AS last_opened,
       MAX(responded_on) AS last_answered,
       (SELECT COUNT(*) FROM holidays) AS holidays_listed
FROM tickets;
