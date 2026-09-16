-- The log at a glance: customers, periods, the dates they run between, and
-- the days you get by adding every period up. Dates are held as YYYY-MM-DD
-- text, which compares and sorts in date order, and both ends of a period
-- are covered days, so a period from the 1st to the 1st is one day long and
-- the length is the difference plus one.
SELECT COUNT(DISTINCT customer) AS customers,
       COUNT(*) AS periods,
       MIN(starts_on) AS first_start,
       MAX(ends_on) AS last_end,
       SUM(CAST(julianday(ends_on) - julianday(starts_on) AS INTEGER) + 1) AS days_added_up
FROM periods;
