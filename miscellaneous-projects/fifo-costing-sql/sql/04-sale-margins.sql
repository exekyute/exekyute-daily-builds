-- What each sale actually earned once its units carry their true FIFO cost:
-- revenue, cost of goods sold summed from the layer allocations, margin, and
-- margin percent. The July 10 sale's margin is lower than its neighbours
-- because 30 of its 70 units came from the dearer 4.50 layer.
-- A sale the layers cannot fully cover stays on the report with its cost and
-- margin left blank and a note counting the uncovered units, rather than
-- pricing those units at zero.
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
           COALESCE(SUM(MIN(l.to_unit, s.to_unit)
                        - MAX(l.from_unit, s.from_unit)), 0) AS units_costed,
           SUM((MIN(l.to_unit, s.to_unit) - MAX(l.from_unit, s.from_unit))
               * l.unit_cost_cents) AS cogs_cents
    FROM sold s
    LEFT JOIN layers l ON l.product = s.product
                      AND l.from_unit < s.to_unit
                      AND s.from_unit < l.to_unit
    GROUP BY s.sale_id, s.product, s.sale_date, s.qty, s.unit_price_cents
)
SELECT sale_id,
       product,
       sale_date,
       qty,
       printf('%.2f', qty * unit_price_cents / 100.0) AS revenue,
       CASE WHEN units_costed = qty
            THEN printf('%.2f', cogs_cents / 100.0)
            END AS cogs,
       CASE WHEN units_costed = qty
            THEN printf('%.2f', (qty * unit_price_cents - cogs_cents) / 100.0)
            END AS margin,
       CASE WHEN units_costed = qty
            THEN printf('%.1f%%', 100.0 * (qty * unit_price_cents - cogs_cents)
                                  / (qty * unit_price_cents))
            END AS margin_pct,
       CASE WHEN units_costed < qty
            THEN printf('%d of %d units have no purchase layer',
                        qty - units_costed, qty)
            ELSE '' END AS note
FROM costed
ORDER BY sale_id;
