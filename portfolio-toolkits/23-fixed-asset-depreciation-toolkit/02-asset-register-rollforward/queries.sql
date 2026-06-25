-- Asset register rollforward queries.
--
-- The pool identity for any CCA class in a year is:
--   opening UCC + additions - disposals - CCA = closing UCC
-- These queries derive opening, additions, disposals, and the asset counts
-- straight from the register, independently of the depreciation engine. The
-- runner takes these aggregates, applies the half-year rule and the class rate
-- with decimal rounding, and reconciles the result to the engine's per_class_cca.csv.

-- name: class_rollforward
-- For each class that has an opening balance or any assets: the opening UCC, the
-- additions placed in service in the tax year, the disposals (the lesser of
-- proceeds and capital cost for each disposed asset), the total assets, and the
-- assets still held at year end. The :year parameter is bound by the runner.
WITH class_list AS (
    SELECT cca_class FROM opening_ucc
    UNION
    SELECT cca_class FROM assets
)
SELECT
    cl.cca_class,
    cc.rate AS rate,
    COALESCE((
        SELECT o.opening_ucc_cents FROM opening_ucc o WHERE o.cca_class = cl.cca_class
    ), 0) AS opening_ucc_cents,
    COALESCE((
        SELECT SUM(a.capital_cost_cents) FROM assets a
        WHERE a.cca_class = cl.cca_class
          AND substr(a.in_service_date, 1, 4) = :year
    ), 0) AS additions_cents,
    COALESCE((
        SELECT SUM(MIN(a.disposal_proceeds_cents, a.capital_cost_cents)) FROM assets a
        WHERE a.cca_class = cl.cca_class
          AND a.disposed = 1
    ), 0) AS disposals_cents,
    (SELECT COUNT(*) FROM assets a WHERE a.cca_class = cl.cca_class) AS assets_total,
    (SELECT COUNT(*) FROM assets a
        WHERE a.cca_class = cl.cca_class AND a.disposed = 0) AS assets_remaining
FROM class_list cl
LEFT JOIN cca_classes cc ON cc.cca_class = cl.cca_class
ORDER BY CAST(cl.cca_class AS REAL), cl.cca_class;

-- name: disposal_detail
-- One row per disposed asset: the proceeds, the capital cost, and the amount
-- taken against the class pool, which is the lesser of the two.
SELECT
    a.asset_id,
    a.cca_class,
    a.disposal_proceeds_cents AS proceeds_cents,
    a.capital_cost_cents AS cost_cents,
    MIN(a.disposal_proceeds_cents, a.capital_cost_cents) AS taken_cents
FROM assets a
WHERE a.disposed = 1
ORDER BY a.asset_id;
