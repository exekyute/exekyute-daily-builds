-- Only the reps the three rules disagree about, each with the reason. Two
-- reasons exist and they are not equally comfortable. A rep inside the top
-- three distinct amounts but below the third place is a defensible judgment
-- call about how wide a prize should be. A rep cut by ROW_NUMBER while
-- posting the exact same number as a rep it kept is not a judgment call at
-- all: the alphabet decided it, and nothing in the data did.
WITH ranked AS (
    SELECT region,
           rep,
           sales_cents,
           ROW_NUMBER() OVER (PARTITION BY region ORDER BY sales_cents DESC, rep) AS rn,
           RANK() OVER (PARTITION BY region ORDER BY sales_cents DESC) AS rk,
           DENSE_RANK() OVER (PARTITION BY region ORDER BY sales_cents DESC) AS dr
    FROM sales
)
SELECT r.region,
       r.rep,
       printf('%.2f', r.sales_cents / 100.0) AS sales,
       r.rn AS row_number_rank,
       r.rk AS rank_rank,
       r.dr AS dense_rank_rank,
       CASE WHEN r.rn > 3 AND r.rk <= 3
            THEN 'cut by the tiebreak at equal sales'
            ELSE 'inside the top three amounts, past the third place' END AS why,
       (SELECT COUNT(*) FROM ranked p
        WHERE p.region = r.region AND p.sales_cents = r.sales_cents AND p.rn <= 3) AS tied_reps_kept
FROM ranked r
WHERE (r.rn <= 3) + (r.rk <= 3) + (r.dr <= 3) BETWEEN 1 AND 2
ORDER BY r.region, r.rn;
