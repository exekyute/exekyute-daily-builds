-- Every product ranked by revenue with its individual slice of the total.
-- The tiebreak on product name matters: two products tie at 60.00, and
-- without a total ordering their ranks, and every running number later built
-- on those ranks, could change from run to run.
SELECT ROW_NUMBER() OVER (ORDER BY revenue_cents DESC, product) AS revenue_rank,
       product,
       ROUND(revenue_cents / 100.0, 2) AS revenue,
       ROUND(100.0 * revenue_cents / SUM(revenue_cents) OVER (), 2) AS pct_of_total
FROM products
ORDER BY revenue_rank;
