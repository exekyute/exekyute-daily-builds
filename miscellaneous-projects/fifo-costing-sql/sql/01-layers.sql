-- Each purchase as a cost layer occupying a range on its product's cumulative
-- unit line. The running SUM turns arrival order into geometry: the first 100
-- beans are units 0 to 100 at 4.00, the next 80 are units 100 to 180 at 4.50,
-- and FIFO becomes a question of which ranges a sale touches. Same-day
-- purchases keep arrival order by purchase_id.
SELECT product,
       purchase_id,
       purchase_date,
       qty,
       printf('%.2f', unit_cost_cents / 100.0) AS unit_cost,
       SUM(qty) OVER w - qty AS from_unit,
       SUM(qty) OVER w AS to_unit
FROM purchases
WINDOW w AS (PARTITION BY product ORDER BY purchase_date, purchase_id
             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
ORDER BY product, from_unit;
