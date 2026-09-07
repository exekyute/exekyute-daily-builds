-- The three functions side by side on the same rows. The two window
-- definitions are the whole lesson. ROW_NUMBER gets a tiebreak on the rep
-- name because it must hand out distinct numbers and would otherwise pick
-- between equals unpredictably. RANK and DENSE_RANK get no tiebreak on
-- purpose: adding one would make every ORDER BY key unique, no two rows
-- would be peers, and both functions would quietly collapse into a second
-- and third copy of ROW_NUMBER.
SELECT region,
       rep,
       printf('%.2f', sales_cents / 100.0) AS sales,
       ROW_NUMBER() OVER ordered AS row_number_rank,
       RANK() OVER tied AS rank_rank,
       DENSE_RANK() OVER tied AS dense_rank_rank
FROM sales
WINDOW ordered AS (PARTITION BY region ORDER BY sales_cents DESC, rep),
       tied AS (PARTITION BY region ORDER BY sales_cents DESC)
ORDER BY region, row_number_rank;
