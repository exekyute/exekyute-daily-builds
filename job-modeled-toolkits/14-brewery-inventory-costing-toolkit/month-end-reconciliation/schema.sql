-- Schema for the month-end reconciliation database.
--
-- Three input tables, one per CSV: the perpetual valuation and the excise
-- summary both come from the costing engine, and the physical count sheet is
-- entered by the warehouse team. A view holds the reconciliation logic so the
-- analytical queries stay short and legible.

CREATE TABLE perpetual (
    sku             TEXT PRIMARY KEY,
    description     TEXT NOT NULL,
    category        TEXT NOT NULL,
    on_hand_qty     REAL NOT NULL,
    stock_unit      TEXT NOT NULL,
    wac_unit_cost   REAL NOT NULL,
    inventory_value REAL NOT NULL,
    integrity_flag  TEXT
);

CREATE TABLE physical_count (
    sku         TEXT PRIMARY KEY,
    counted_qty REAL NOT NULL
);

CREATE TABLE excise_summary (
    abv_class   TEXT PRIMARY KEY,
    hectolitres REAL NOT NULL,
    excise_duty REAL NOT NULL
);

-- Reconciliation view: one row per SKU found in either source. A SKU missing
-- from the count, or one counted with no perpetual record, is surfaced rather
-- than dropped by the join. Value variance is quantity variance priced at the
-- weighted-average cost, and the $20.00 tolerance decides the status.
CREATE VIEW reconciliation AS
WITH joined AS (
    SELECT p.sku           AS sku,
           p.category      AS category,
           p.on_hand_qty   AS on_hand_qty,
           c.counted_qty   AS counted_qty,
           p.wac_unit_cost AS wac_unit_cost
    FROM perpetual p
    LEFT JOIN physical_count c ON p.sku = c.sku
    UNION ALL
    SELECT c.sku, NULL, NULL, c.counted_qty, NULL
    FROM physical_count c
    LEFT JOIN perpetual p ON c.sku = p.sku
    WHERE p.sku IS NULL
)
SELECT
    sku,
    category,
    on_hand_qty,
    counted_qty,
    CASE WHEN on_hand_qty IS NULL OR counted_qty IS NULL
         THEN NULL
         ELSE ROUND(counted_qty - on_hand_qty, 4)
    END AS qty_variance,
    CASE WHEN on_hand_qty IS NULL OR counted_qty IS NULL
         THEN NULL
         ELSE ROUND((counted_qty - on_hand_qty) * wac_unit_cost, 2)
    END AS value_variance,
    CASE
        WHEN counted_qty IS NULL THEN 'not counted'
        WHEN on_hand_qty IS NULL THEN 'no perpetual record'
        WHEN ABS((counted_qty - on_hand_qty) * wac_unit_cost) > 20.0 THEN 'over tolerance'
        ELSE 'ok'
    END AS status
FROM joined;
