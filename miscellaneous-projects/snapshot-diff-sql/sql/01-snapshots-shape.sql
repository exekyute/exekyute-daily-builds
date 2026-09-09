-- Both snapshots at a glance. The two counts that matter most are the last
-- two: eleven SKUs appear in both files and fifteen appear in either, so
-- four SKUs live on one side only and eleven have to be compared field by
-- field. The unset prices are counted here because they are what breaks the
-- obvious way of doing that comparison.
SELECT (SELECT COUNT(*) FROM prices_before) AS rows_before,
       (SELECT COUNT(*) FROM prices_after) AS rows_after,
       (SELECT COUNT(*) FROM prices_before WHERE price_cents IS NULL) AS unset_price_before,
       (SELECT COUNT(*) FROM prices_after WHERE price_cents IS NULL) AS unset_price_after,
       (SELECT COUNT(*) FROM (SELECT sku FROM prices_before
                              INTERSECT
                              SELECT sku FROM prices_after)) AS skus_in_both,
       (SELECT COUNT(*) FROM (SELECT sku FROM prices_before
                              UNION
                              SELECT sku FROM prices_after)) AS skus_in_either;
