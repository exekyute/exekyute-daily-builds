-- Every rep that at least one top-three rule selects, with a column per
-- rule. The three rules read the same cutoff differently: ROW_NUMBER means
-- the first three rows, RANK means everyone standing in the first three
-- places, and DENSE_RANK means everyone inside the first three distinct
-- amounts. Reps whose three cells disagree are where a real payout
-- decision would have to be made on purpose instead of by accident.
WITH ranked AS (
    SELECT region,
           rep,
           sales_cents,
           ROW_NUMBER() OVER (PARTITION BY region ORDER BY sales_cents DESC, rep) AS rn,
           RANK() OVER (PARTITION BY region ORDER BY sales_cents DESC) AS rk,
           DENSE_RANK() OVER (PARTITION BY region ORDER BY sales_cents DESC) AS dr
    FROM sales
)
SELECT region,
       rep,
       printf('%.2f', sales_cents / 100.0) AS sales,
       rn AS row_number_rank,
       rk AS rank_rank,
       dr AS dense_rank_rank,
       CASE WHEN rn <= 3 THEN 'yes' ELSE '' END AS by_row_number,
       CASE WHEN rk <= 3 THEN 'yes' ELSE '' END AS by_rank,
       CASE WHEN dr <= 3 THEN 'yes' ELSE '' END AS by_dense_rank
FROM ranked
WHERE rn <= 3 OR rk <= 3 OR dr <= 3
ORDER BY region, rn;
