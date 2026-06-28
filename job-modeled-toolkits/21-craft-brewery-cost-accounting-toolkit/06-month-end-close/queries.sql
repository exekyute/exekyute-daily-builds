-- Analytical queries for the month-end close. The runner splits this file on
-- the "-- @name" markers and runs each query in turn, printing the results and
-- checking the totals against the hand-checked figures in spec.md.
--
-- The tolerance for a count variance is $50.00 of value. Anything past that, plus
-- any SKU carrying a data-integrity flag, is an exception.

-- @valuation_total
-- Total book inventory value. This must equal the perpetual valuation tool.
SELECT ROUND(SUM(inventory_value), 2) AS total_inventory_value
FROM perpetual;

-- @valuation_by_category
-- Book inventory value split by category.
SELECT category, ROUND(SUM(inventory_value), 2) AS category_value
FROM perpetual
GROUP BY category
ORDER BY category;

-- @reconciliation
-- Book quantity against the physical count, with the value of the variance and
-- whether it is past the $50.00 tolerance.
SELECT p.sku,
       p.category,
       p.on_hand_qty AS book_qty,
       c.counted_qty,
       ROUND(c.counted_qty - p.on_hand_qty, 4) AS qty_variance,
       ROUND((c.counted_qty - p.on_hand_qty) * p.wac_unit_cost, 2) AS value_variance,
       CASE
           WHEN ABS((c.counted_qty - p.on_hand_qty) * p.wac_unit_cost) > 50
           THEN 'over tolerance'
           ELSE 'within tolerance'
       END AS status
FROM perpetual p
JOIN physical_count c ON c.sku = p.sku
ORDER BY p.sku;

-- @exceptions
-- Everything that needs a person to look at it: count variances past tolerance,
-- and SKUs carrying an integrity flag such as a negative on-hand balance.
SELECT sku, reason, detail
FROM (
    SELECT p.sku AS sku,
           'count variance over tolerance' AS reason,
           'value variance ' || ROUND((c.counted_qty - p.on_hand_qty) * p.wac_unit_cost, 2) AS detail,
           1 AS ord
    FROM perpetual p
    JOIN physical_count c ON c.sku = p.sku
    WHERE ABS((c.counted_qty - p.on_hand_qty) * p.wac_unit_cost) > 50
    UNION ALL
    SELECT sku, 'integrity flag' AS reason, integrity_flag AS detail, 2 AS ord
    FROM perpetual
    WHERE integrity_flag <> ''
)
ORDER BY ord, sku;

-- @excise_total
-- Total federal excise duty. This must equal the excise duty engine.
SELECT ROUND(SUM(excise_duty), 2) AS total_excise_duty
FROM excise_summary;

-- @journal_entries
-- The closing journal entries built from the period's data: sales, cost of goods
-- sold, excise duty, and the adjustment that writes book inventory to the
-- physical count. Each entry has equal debits and credits.
WITH agg AS (
    SELECT (SELECT ROUND(SUM(revenue), 2) FROM sku_margins) AS revenue,
           (SELECT ROUND(SUM(cogs_total), 2) FROM sku_margins) AS cogs,
           (SELECT ROUND(SUM(excise_duty), 2) FROM excise_summary) AS excise,
           (SELECT ROUND(SUM((c.counted_qty - p.on_hand_qty) * p.wac_unit_cost), 2)
            FROM perpetual p JOIN physical_count c ON c.sku = p.sku) AS net_var
)
SELECT account, ROUND(debit, 2) AS debit, ROUND(credit, 2) AS credit, memo
FROM (
    SELECT 1 AS ord, '1100 Accounts Receivable' AS account, revenue AS debit, 0 AS credit,
           'Sales for the period' AS memo FROM agg
    UNION ALL SELECT 2, '4000 Sales Revenue', 0, revenue, 'Sales for the period' FROM agg
    UNION ALL SELECT 3, '5000 Cost of Goods Sold', cogs, 0, 'COGS on units sold' FROM agg
    UNION ALL SELECT 4, '1500 Finished Goods Inventory', 0, cogs, 'COGS on units sold' FROM agg
    UNION ALL SELECT 5, '5200 Excise Duty Expense', excise, 0, 'Federal beer excise on packaged volume' FROM agg
    UNION ALL SELECT 6, '2100 Excise Duty Payable', 0, excise, 'Federal beer excise on packaged volume' FROM agg
    UNION ALL SELECT 7, '5100 Inventory Count Adjustment',
           CASE WHEN net_var < 0 THEN -net_var ELSE 0 END,
           CASE WHEN net_var > 0 THEN net_var ELSE 0 END,
           'Write book inventory to physical count' FROM agg
    UNION ALL SELECT 8, '1300 Materials and Packaging Inventory',
           CASE WHEN net_var > 0 THEN net_var ELSE 0 END,
           CASE WHEN net_var < 0 THEN -net_var ELSE 0 END,
           'Write book inventory to physical count' FROM agg
)
ORDER BY ord;

-- @trial_balance
-- Total debits and total credits, summed separately across the same closing
-- entries. A balanced close has the two equal.
WITH agg AS (
    SELECT (SELECT ROUND(SUM(revenue), 2) FROM sku_margins) AS revenue,
           (SELECT ROUND(SUM(cogs_total), 2) FROM sku_margins) AS cogs,
           (SELECT ROUND(SUM(excise_duty), 2) FROM excise_summary) AS excise,
           (SELECT ROUND(SUM((c.counted_qty - p.on_hand_qty) * p.wac_unit_cost), 2)
            FROM perpetual p JOIN physical_count c ON c.sku = p.sku) AS net_var
),
je AS (
    SELECT revenue AS debit, 0 AS credit FROM agg
    UNION ALL SELECT 0, revenue FROM agg
    UNION ALL SELECT cogs, 0 FROM agg
    UNION ALL SELECT 0, cogs FROM agg
    UNION ALL SELECT excise, 0 FROM agg
    UNION ALL SELECT 0, excise FROM agg
    UNION ALL SELECT CASE WHEN net_var < 0 THEN -net_var ELSE 0 END,
                     CASE WHEN net_var > 0 THEN net_var ELSE 0 END FROM agg
    UNION ALL SELECT CASE WHEN net_var > 0 THEN net_var ELSE 0 END,
                     CASE WHEN net_var < 0 THEN -net_var ELSE 0 END FROM agg
)
SELECT ROUND(SUM(debit), 2) AS total_debits, ROUND(SUM(credit), 2) AS total_credits
FROM je;
