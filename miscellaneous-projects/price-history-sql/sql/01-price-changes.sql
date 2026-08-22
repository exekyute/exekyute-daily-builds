-- The snapshots where a product's price differs from its previous snapshot.
-- LAG pulls the prior price onto each row; the first snapshot per product has
-- no prior and counts as a change too, so every product gets an opening row.
WITH ordered AS (
    SELECT product,
           snapshot_date,
           price,
           LAG(price) OVER (PARTITION BY product ORDER BY snapshot_date) AS prev_price
    FROM price_snapshots
)
SELECT product,
       snapshot_date,
       CASE WHEN prev_price IS NULL THEN NULL ELSE printf('%.2f', prev_price) END          AS prev_price,
       printf('%.2f', price)                                                              AS price,
       CASE WHEN prev_price IS NULL THEN NULL ELSE printf('%+.2f', price - prev_price) END AS change
FROM ordered
WHERE prev_price IS NULL OR price <> prev_price
ORDER BY product, snapshot_date;
