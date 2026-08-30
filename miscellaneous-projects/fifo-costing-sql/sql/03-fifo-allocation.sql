-- The FIFO engine in one join: a sale draws from every layer whose range
-- overlaps its own, and the units drawn are the length of the intersection,
-- MIN of the ends minus MAX of the starts. No loops, no running depletion
-- state: the cumulative lines already encode first-in-first-out, so a plain
-- interval intersection does the allocation. Costs multiply in integer cents.
WITH layers AS (
    SELECT product, purchase_id, purchase_date, unit_cost_cents,
           SUM(qty) OVER w - qty AS from_unit,
           SUM(qty) OVER w AS to_unit
    FROM purchases
    WINDOW w AS (PARTITION BY product ORDER BY purchase_date, purchase_id
                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
),
sold AS (
    SELECT product, sale_id, sale_date,
           SUM(qty) OVER w - qty AS from_unit,
           SUM(qty) OVER w AS to_unit
    FROM sales
    WINDOW w AS (PARTITION BY product ORDER BY sale_date, sale_id
                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
)
SELECT s.product,
       s.sale_id,
       s.sale_date,
       l.purchase_date AS layer_date,
       MIN(l.to_unit, s.to_unit) - MAX(l.from_unit, s.from_unit) AS units,
       printf('%.2f', l.unit_cost_cents / 100.0) AS unit_cost,
       printf('%.2f', (MIN(l.to_unit, s.to_unit) - MAX(l.from_unit, s.from_unit))
                      * l.unit_cost_cents / 100.0) AS layer_cost
FROM sold s
JOIN layers l ON l.product = s.product
             AND l.from_unit < s.to_unit
             AND s.from_unit < l.to_unit
ORDER BY s.product, s.sale_id, l.from_unit;
