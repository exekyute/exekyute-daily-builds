-- What each order actually paid: join every order to the price version whose
-- range covers the order date. The LEFT JOIN keeps orders placed before the
-- first snapshot, which come back with no price and a note instead of
-- silently disappearing.
WITH ordered AS (
    SELECT product,
           snapshot_date,
           price,
           LAG(price) OVER (PARTITION BY product ORDER BY snapshot_date) AS prev_price
    FROM price_snapshots
),
changes AS (
    SELECT product, snapshot_date AS valid_from, price
    FROM ordered
    WHERE prev_price IS NULL OR price <> prev_price
),
history AS (
    SELECT product,
           valid_from,
           DATE(LEAD(valid_from) OVER (PARTITION BY product ORDER BY valid_from), '-1 day') AS valid_to,
           price
    FROM changes
)
SELECT o.order_id,
       o.product,
       o.order_date,
       o.qty,
       CASE WHEN h.price IS NULL THEN NULL ELSE printf('%.2f', h.price) END        AS unit_price,
       CASE WHEN h.price IS NULL THEN NULL ELSE printf('%.2f', o.qty * h.price) END AS line_total,
       CASE WHEN h.price IS NULL THEN 'no price on file' ELSE '' END              AS note
FROM orders o
LEFT JOIN history h
       ON h.product = o.product
      AND h.valid_from <= o.order_date
      AND (h.valid_to IS NULL OR h.valid_to >= o.order_date)
ORDER BY o.order_id;
