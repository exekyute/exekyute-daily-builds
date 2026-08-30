-- What each sale actually earned once its units carry their true FIFO cost:
-- revenue, cost of goods sold summed from the layer allocations, margin, and
-- margin percent. The July 10 sale's margin is lower than its neighbours
-- because 30 of its 70 units came from the dearer 4.50 layer.
WITH layers AS (
    SELECT product, unit_cost_cents,
           SUM(qty) OVER w - qty AS from_unit,
           SUM(qty) OVER w AS to_unit
    FROM purchases
    WINDOW w AS (PARTITION BY product ORDER BY purchase_date, purchase_id
                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
),
sold AS (
    SELECT product, sale_id, sale_date, qty, unit_price_cents,
           SUM(qty) OVER w - qty AS from_unit,
           SUM(qty) OVER w AS to_unit
    FROM sales
    WINDOW w AS (PARTITION BY product ORDER BY sale_date, sale_id
                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
),
costed AS (
    SELECT s.sale_id, s.product, s.sale_date, s.qty, s.unit_price_cents,
           SUM((MIN(l.to_unit, s.to_unit) - MAX(l.from_unit, s.from_unit))
               * l.unit_cost_cents) AS cogs_cents
    FROM sold s
    JOIN layers l ON l.product = s.product
                 AND l.from_unit < s.to_unit
                 AND s.from_unit < l.to_unit
    GROUP BY s.sale_id, s.product, s.sale_date, s.qty, s.unit_price_cents
)
SELECT sale_id,
       product,
       sale_date,
       qty,
       printf('%.2f', qty * unit_price_cents / 100.0) AS revenue,
       printf('%.2f', cogs_cents / 100.0) AS cogs,
       printf('%.2f', (qty * unit_price_cents - cogs_cents) / 100.0) AS margin,
       printf('%.1f%%', 100.0 * (qty * unit_price_cents - cogs_cents)
                        / (qty * unit_price_cents)) AS margin_pct
FROM costed
ORDER BY sale_id;
