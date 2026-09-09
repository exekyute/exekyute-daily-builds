-- The trap, laid open. Joining the snapshots on SKU and comparing columns
-- with <> is the obvious way to find changes, and it silently loses every
-- row where a value entered or left the unset state. NULL <> 12.00 is not
-- true and not false, it is NULL, so the CASE falls through to its ELSE and
-- reports the row as unchanged. IS NOT is the same comparison with NULL
-- treated as a value, and it is the only difference between these two
-- columns. Four changes under the naive rule, six under the honest one.
-- The price columns carry a second helping of the same lesson: printf
-- renders NULL as 0.00 rather than returning NULL, so wrapping it in
-- COALESCE never fires and an unset price prints as a real-looking
-- zero. The NULL has to be caught before the formatting, not after.
SELECT b.sku,
       b.description AS description_before,
       a.description AS description_after,
       CASE WHEN b.price_cents IS NULL THEN 'not set'
            ELSE printf('%.2f', b.price_cents / 100.0) END AS price_before,
       CASE WHEN a.price_cents IS NULL THEN 'not set'
            ELSE printf('%.2f', a.price_cents / 100.0) END AS price_after,
       CASE WHEN b.description <> a.description OR b.price_cents <> a.price_cents
            THEN 'changed' ELSE 'unchanged' END AS naive_verdict,
       CASE WHEN b.description IS NOT a.description OR b.price_cents IS NOT a.price_cents
            THEN 'changed' ELSE 'unchanged' END AS null_safe_verdict
FROM prices_before b
JOIN prices_after a ON a.sku = b.sku
ORDER BY b.sku;
