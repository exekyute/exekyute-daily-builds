-- Collapse the change rows into one row per price version with a date range.
-- valid_from is the snapshot that first showed the price; valid_to is the day
-- before the next version starts, via LEAD, and stays NULL on the current one.
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
           ROW_NUMBER() OVER (PARTITION BY product ORDER BY valid_from) AS version,
           valid_from,
           DATE(LEAD(valid_from) OVER (PARTITION BY product ORDER BY valid_from), '-1 day') AS valid_to,
           price
    FROM changes
)
SELECT product,
       version,
       valid_from,
       valid_to,
       printf('%.2f', price) AS price
FROM history
ORDER BY product, valid_from;
