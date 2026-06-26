-- Analytical queries for month-end. Each is named with a "-- @name" marker so
-- the runner can pick it out, and commented with the plain question it answers.
-- The numbers round to the cent the same way the costing engine does, so the
-- two tools agree.

-- @reconciliation
-- Every SKU, its book-to-count variance, and whether it clears tolerance.
SELECT sku, on_hand_qty, counted_qty, qty_variance, value_variance, status
FROM reconciliation
ORDER BY sku;

-- @exceptions
-- Only the SKUs that need a second look: missing, unexpected, or out of tolerance.
SELECT sku, qty_variance, value_variance, status
FROM reconciliation
WHERE status <> 'ok'
ORDER BY sku;

-- @valuation_by_category
-- Closing inventory value grouped the way the balance sheet wants it.
SELECT category, ROUND(SUM(inventory_value), 2) AS total_value
FROM perpetual
GROUP BY category
ORDER BY category;

-- @valuation_total
-- One number: the closing inventory value across every SKU.
SELECT ROUND(SUM(inventory_value), 2) AS total_inventory_value
FROM perpetual;

-- @excise_by_class
-- Hectolitres packaged and excise duty owed, split by ABV class.
SELECT abv_class,
       ROUND(SUM(hectolitres), 2) AS hectolitres,
       ROUND(SUM(excise_duty), 2) AS excise_duty
FROM excise_summary
GROUP BY abv_class
ORDER BY abv_class;

-- @excise_total
-- One number: total federal excise duty for the period.
SELECT ROUND(SUM(excise_duty), 2) AS total_excise_duty
FROM excise_summary;
