-- The changed rows, and the reason to reach for EXCEPT rather than write
-- the comparison by hand. EXCEPT compares whole rows with NULL treated as a
-- value, across every column at once, so the two rows that query 02 lost
-- come back without anyone remembering to write IS NOT. Three columns need
-- no care here; thirty would need thirty correct hand-written comparisons.
-- Joining the result back to the later snapshot drops the removed SKUs,
-- since those have nothing on the other side to have changed into.
WITH before_rows_not_in_after AS (
    SELECT sku, description, price_cents FROM prices_before
    EXCEPT
    SELECT sku, description, price_cents FROM prices_after
)
SELECT b.sku,
       b.description AS description_before,
       a.description AS description_after,
       CASE WHEN b.price_cents IS NULL THEN 'not set'
            ELSE printf('%.2f', b.price_cents / 100.0) END AS price_before,
       CASE WHEN a.price_cents IS NULL THEN 'not set'
            ELSE printf('%.2f', a.price_cents / 100.0) END AS price_after,
       TRIM(CASE WHEN b.description IS NOT a.description THEN 'description ' ELSE '' END ||
            CASE WHEN b.price_cents IS NOT a.price_cents THEN 'price' ELSE '' END) AS fields_changed
FROM before_rows_not_in_after b
JOIN prices_after a ON a.sku = b.sku
ORDER BY b.sku;
