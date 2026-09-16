-- The two answers people reach for first, each right only under a
-- condition the log does not promise.
--
-- days_added_up sums the length of every period. Where periods overlap it
-- counts the same day twice, so a customer who renewed early looks covered
-- for longer than the calendar allows. It is right when nothing overlaps.
--
-- span_days takes the first start to the last end and treats it as one
-- stretch. That paves over every lapse in between, so a customer who let
-- the cover drop still reads as covered throughout. It is right when
-- nothing lapses.
--
-- Whichever happened to be right, this query cannot say which, and a
-- customer with both an overlap and a lapse has neither. Query 04 works
-- out the covered days and how far each of these was out.
SELECT customer,
       COUNT(*) AS periods,
       MIN(starts_on) AS first_start,
       MAX(ends_on) AS last_end,
       SUM(CAST(julianday(ends_on) - julianday(starts_on) AS INTEGER) + 1) AS days_added_up,
       CAST(julianday(MAX(ends_on)) - julianday(MIN(starts_on)) AS INTEGER) + 1 AS span_days
FROM periods
GROUP BY customer
ORDER BY customer;
