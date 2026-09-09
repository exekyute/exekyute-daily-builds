-- The SKUs that exist on one side only, from EXCEPT in both directions.
-- EXCEPT answers set questions directly: rows of the first query that have
-- no match in the second. Written the other common way, as NOT IN against a
-- subquery, the same question returns nothing at all the moment that
-- subquery yields a single NULL, because a value compared to NULL is never
-- unequal, only unknown. EXCEPT has no such failure mode.
SELECT * FROM (
    SELECT 'added' AS change,
           a.sku,
           a.description,
           CASE WHEN a.price_cents IS NULL THEN 'not set'
                ELSE printf('%.2f', a.price_cents / 100.0) END AS price
    FROM prices_after a
    WHERE a.sku IN (SELECT sku FROM prices_after
                    EXCEPT
                    SELECT sku FROM prices_before)
    UNION ALL
    SELECT 'removed',
           b.sku,
           b.description,
           CASE WHEN b.price_cents IS NULL THEN 'not set'
                ELSE printf('%.2f', b.price_cents / 100.0) END
    FROM prices_before b
    WHERE b.sku IN (SELECT sku FROM prices_before
                    EXCEPT
                    SELECT sku FROM prices_after)
)
ORDER BY change, sku;
