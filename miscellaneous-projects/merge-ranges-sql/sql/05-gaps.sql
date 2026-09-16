-- The lapses themselves. Once the periods are merged, a gap is the space
-- between one block and the next: it opens the day after a block ends and
-- closes the day before the next one starts, so its length is the number
-- of days from the end of one block to the start of the next, less the one
-- day the ending block still covers.
--
-- LEAD reads the next block for each row, and the last block of a customer
-- has none, so it drops out and a customer covered throughout shows no
-- rows at all.
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
    SELECT customer, block, MIN(starts_on) AS starts_on, MAX(ends_on) AS ends_on
    FROM blocked
    GROUP BY customer, block
),
paired AS (
    SELECT customer, ends_on,
           LEAD(starts_on) OVER (PARTITION BY customer ORDER BY starts_on) AS next_start
    FROM blocks
)
SELECT customer,
       DATE(ends_on, '+1 day') AS gap_from,
       DATE(next_start, '-1 day') AS gap_to,
       CAST(julianday(next_start) - julianday(ends_on) AS INTEGER) - 1 AS days
FROM paired
WHERE next_start IS NOT NULL
ORDER BY customer, gap_from;
