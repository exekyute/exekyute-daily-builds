-- Every product's price on one report date. The as-of date is pinned so the
-- sample data gives the same answer every run; swap it for DATE('now') against
-- live data. A version matches when the date falls inside its range, with an
-- open valid_to meaning "still current".
WITH params AS (
    SELECT DATE('2026-07-20') AS as_of
),
ordered AS (
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
SELECT h.product,
       printf('%.2f', h.price) AS price,
       h.valid_from,
       h.valid_to
FROM history h
CROSS JOIN params p
WHERE h.valid_from <= p.as_of
  AND (h.valid_to IS NULL OR h.valid_to >= p.as_of)
ORDER BY h.product;
