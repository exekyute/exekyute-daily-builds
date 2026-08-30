-- Two proofs per product, in cents so equality is exact. First, conservation:
-- everything purchased is either sold or still on the shelf, so purchase
-- value equals cost of goods sold plus ending inventory. Second, coverage:
-- every sale found enough layer units to fully allocate. A FAIL in the second
-- check means overselling, units sold that no purchase backs.
WITH layers AS (
    SELECT product, unit_cost_cents, qty,
           SUM(qty) OVER w - qty AS from_unit,
           SUM(qty) OVER w AS to_unit
    FROM purchases
    WINDOW w AS (PARTITION BY product ORDER BY purchase_date, purchase_id
                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
),
sold AS (
    SELECT product, sale_id, qty,
           SUM(qty) OVER w - qty AS from_unit,
           SUM(qty) OVER w AS to_unit
    FROM sales
    WINDOW w AS (PARTITION BY product ORDER BY sale_date, sale_id
                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
),
allocations AS (
    SELECT s.product, s.sale_id, s.qty,
           SUM(MIN(l.to_unit, s.to_unit) - MAX(l.from_unit, s.from_unit)) AS units,
           SUM((MIN(l.to_unit, s.to_unit) - MAX(l.from_unit, s.from_unit))
               * l.unit_cost_cents) AS cogs_cents
    FROM sold s
    JOIN layers l ON l.product = s.product
                 AND l.from_unit < s.to_unit
                 AND s.from_unit < l.to_unit
    GROUP BY s.product, s.sale_id, s.qty
),
sold_totals AS (
    SELECT product, SUM(qty) AS units_sold
    FROM sales
    GROUP BY product
),
per_product AS (
    SELECT l.product,
           SUM(l.qty * l.unit_cost_cents) AS purchased_cents,
           COALESCE((SELECT SUM(a.cogs_cents) FROM allocations a
                     WHERE a.product = l.product), 0) AS cogs_cents,
           SUM(MAX(0, l.to_unit - MAX(l.from_unit, COALESCE(st.units_sold, 0)))
               * l.unit_cost_cents) AS ending_cents
    FROM layers l
    LEFT JOIN sold_totals st ON st.product = l.product
    GROUP BY l.product
),
shortfalls AS (
    -- LEFT JOIN from sales, not from allocations: a sale with no backing
    -- layers at all has no allocation rows, and it must count as short
    -- rather than vanish from the one check meant to catch it.
    SELECT s.product, COUNT(*) AS sales_count,
           SUM(s.qty <> COALESCE(a.units, 0)) AS short_sales
    FROM sales s
    LEFT JOIN allocations a ON a.sale_id = s.sale_id
    GROUP BY s.product
)
SELECT 'purchases equal cogs plus ending stock' AS check_name,
       p.product,
       printf('%.2f = %.2f + %.2f',
              p.purchased_cents / 100.0, p.cogs_cents / 100.0, p.ending_cents / 100.0) AS detail,
       CASE WHEN p.purchased_cents = p.cogs_cents + p.ending_cents
            THEN 'ok' ELSE 'FAIL' END AS status
FROM per_product p
UNION ALL
SELECT 'every sale fully allocated',
       s.product,
       s.sales_count || ' sales, ' || s.short_sales || ' short',
       CASE WHEN s.short_sales = 0 THEN 'ok' ELSE 'FAIL' END
FROM shortfalls s
ORDER BY check_name, product;
