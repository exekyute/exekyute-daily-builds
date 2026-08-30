-- Each sale as a range on the same cumulative unit line, counted over units
-- sold so far. The 70-unit sale on July 10 occupies units 60 to 130, and one
-- glance at the layer ranges says it must straddle the 4.00 and 4.50 stock.
SELECT product,
       sale_id,
       sale_date,
       qty,
       printf('%.2f', unit_price_cents / 100.0) AS unit_price,
       SUM(qty) OVER w - qty AS from_unit,
       SUM(qty) OVER w AS to_unit
FROM sales
WINDOW w AS (PARTITION BY product ORDER BY sale_date, sale_id
             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
ORDER BY product, from_unit;
