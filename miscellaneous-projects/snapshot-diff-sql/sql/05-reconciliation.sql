-- The closing line. Four buckets, built from EXCEPT and INTERSECT, that
-- have to partition the fifteen SKUs appearing in either file exactly once
-- each. The reconciliation column is the check: if the four counts miss the
-- union total, the diff has double-counted or dropped something and no
-- other number on the page can be trusted. The last column is the cost of
-- the shortcut, the changed rows the naive comparison in query 02 reports
-- as unchanged.
WITH universe AS (
    SELECT sku FROM prices_before
    UNION
    SELECT sku FROM prices_after
),
added AS (
    SELECT sku FROM prices_after
    EXCEPT
    SELECT sku FROM prices_before
),
removed AS (
    SELECT sku FROM prices_before
    EXCEPT
    SELECT sku FROM prices_after
),
unchanged AS (
    SELECT sku FROM (
        SELECT sku, description, price_cents FROM prices_before
        INTERSECT
        SELECT sku, description, price_cents FROM prices_after)
),
changed AS (
    SELECT sku FROM universe
    EXCEPT
    SELECT sku FROM added
    EXCEPT
    SELECT sku FROM removed
    EXCEPT
    SELECT sku FROM unchanged
)
SELECT (SELECT COUNT(*) FROM added) AS added,
       (SELECT COUNT(*) FROM removed) AS removed,
       (SELECT COUNT(*) FROM changed) AS changed,
       (SELECT COUNT(*) FROM unchanged) AS unchanged,
       (SELECT COUNT(*) FROM universe) AS skus_in_either,
       CASE WHEN (SELECT COUNT(*) FROM added) + (SELECT COUNT(*) FROM removed)
                 + (SELECT COUNT(*) FROM changed) + (SELECT COUNT(*) FROM unchanged)
                 = (SELECT COUNT(*) FROM universe)
            THEN 'balances' ELSE 'does not balance' END AS reconciliation,
       (SELECT COUNT(*) FROM changed c
        JOIN prices_before b ON b.sku = c.sku
        JOIN prices_after a ON a.sku = c.sku
        WHERE COALESCE(b.description <> a.description
                       OR b.price_cents <> a.price_cents, 0) = 0
       ) AS missed_by_naive_compare;
