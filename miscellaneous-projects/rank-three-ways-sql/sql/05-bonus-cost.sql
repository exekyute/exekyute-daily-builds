-- What the choice costs, at a flat 1,000.00 bonus for every rep the rule
-- selects. The same sentence, top three reps in each region, funds twelve
-- people under one rule and seventeen under another, a 5,000.00 spread that
-- lives entirely in which window function someone typed. The last column
-- says what each rule is actually for, which is the only sound way to pick.
WITH ranked AS (
    SELECT region,
           ROW_NUMBER() OVER (PARTITION BY region ORDER BY sales_cents DESC, rep) AS rn,
           RANK() OVER (PARTITION BY region ORDER BY sales_cents DESC) AS rk,
           DENSE_RANK() OVER (PARTITION BY region ORDER BY sales_cents DESC) AS dr
    FROM sales
),
counted AS (
    SELECT SUM(CASE WHEN rn <= 3 THEN 1 ELSE 0 END) AS by_rn,
           SUM(CASE WHEN rk <= 3 THEN 1 ELSE 0 END) AS by_rk,
           SUM(CASE WHEN dr <= 3 THEN 1 ELSE 0 END) AS by_dr
    FROM ranked
),
lines AS (
    SELECT 1 AS seq, 'ROW_NUMBER' AS rule, by_rn AS reps_paid,
           'exactly three prizes, tiebreak decides' AS fits FROM counted
    UNION ALL
    SELECT 2, 'RANK', by_rk, 'three places, ties share a place' FROM counted
    UNION ALL
    SELECT 3, 'DENSE_RANK', by_dr, 'three amount tiers, ties share a tier' FROM counted
)
SELECT rule,
       reps_paid,
       printf('%.2f', reps_paid * 100000 / 100.0) AS bonus_cost,
       fits
FROM lines
ORDER BY seq;
