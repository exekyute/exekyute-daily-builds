-- What each customer was actually covered for, next to the two numbers
-- query 02 offered. Covered days is the merged blocks added up, which
-- counts every covered day once. The gap between that and the added-up
-- total is the surplus the adding up carried, so a day covered by three
-- periods adds two to it rather than one, and the gap between the span and
-- the covered days is days with no cover at all inside the customer's own
-- first and last dates.
--
-- A customer whose periods never overlap has 0 double counted, and one
-- whose cover never lapses has 0 uncovered, so the two columns say which
-- of query 02's answers went wrong and by how much.
WITH ordered AS (
    SELECT customer, period_id, starts_on, ends_on,
           MAX(ends_on) OVER (PARTITION BY customer ORDER BY starts_on, ends_on, period_id
                              ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS covered_to
    FROM periods
),
flagged AS (
    SELECT customer, period_id, starts_on, ends_on,
           CASE WHEN covered_to IS NULL OR starts_on > DATE(covered_to, '+1 day') THEN 1 ELSE 0 END AS opens_block
    FROM ordered
),
blocked AS (
    SELECT customer, starts_on, ends_on,
           SUM(opens_block) OVER (PARTITION BY customer ORDER BY starts_on, ends_on, period_id
                                  ROWS UNBOUNDED PRECEDING) AS block
    FROM flagged
),
blocks AS (
    SELECT customer, block, MIN(starts_on) AS starts_on, MAX(ends_on) AS ends_on,
           CAST(julianday(MAX(ends_on)) - julianday(MIN(starts_on)) AS INTEGER) + 1 AS days
    FROM blocked
    GROUP BY customer, block
),
covered AS (
    SELECT customer, COUNT(*) AS blocks, SUM(days) AS covered_days,
           CAST(julianday(MAX(ends_on)) - julianday(MIN(starts_on)) AS INTEGER) + 1 AS span_days
    FROM blocks
    GROUP BY customer
),
added AS (
    SELECT customer, COUNT(*) AS periods,
           SUM(CAST(julianday(ends_on) - julianday(starts_on) AS INTEGER) + 1) AS days_added_up
    FROM periods
    GROUP BY customer
)
SELECT a.customer,
       a.periods,
       c.blocks,
       a.days_added_up,
       c.covered_days,
       a.days_added_up - c.covered_days AS days_counted_twice,
       c.span_days - c.covered_days AS days_not_covered
FROM added a
JOIN covered c ON c.customer = a.customer
ORDER BY a.customer;
