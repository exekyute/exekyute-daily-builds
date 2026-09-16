-- The merge. Periods are read in start order, and each one is compared
-- with how far cover already reaches: the MAX of every end date before it,
-- taken with a frame that stops one row short of the current one. A period
-- opens a new block when nothing comes before it, or when it starts more
-- than a day after that reach,
-- since a period starting the day after the last one ends continues the
-- cover rather than breaking it.
--
-- The running MAX is what makes containment safe. Comparing with the
-- previous row alone would break a long period that has a short one inside
-- it: the row after the short one would look like a fresh start, even
-- though the long period still has it covered.
--
-- Flagging the openers and running a SUM over the flag numbers the blocks,
-- and grouping by that number gives each block its dates and its length.
WITH ordered AS (
    SELECT customer,
           period_id,
           starts_on,
           ends_on,
           MAX(ends_on) OVER (PARTITION BY customer ORDER BY starts_on, ends_on, period_id
                              ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS covered_to
    FROM periods
),
flagged AS (
    SELECT customer,
           period_id,
           starts_on,
           ends_on,
           CASE WHEN covered_to IS NULL OR starts_on > DATE(covered_to, '+1 day') THEN 1 ELSE 0 END AS opens_block
    FROM ordered
),
blocked AS (
    SELECT customer,
           starts_on,
           ends_on,
           SUM(opens_block) OVER (PARTITION BY customer ORDER BY starts_on, ends_on, period_id
                                  ROWS UNBOUNDED PRECEDING) AS block
    FROM flagged
)
SELECT customer,
       block,
       MIN(starts_on) AS starts_on,
       MAX(ends_on) AS ends_on,
       COUNT(*) AS periods,
       CAST(julianday(MAX(ends_on)) - julianday(MIN(starts_on)) AS INTEGER) + 1 AS days
FROM blocked
GROUP BY customer, block
ORDER BY customer, block;
