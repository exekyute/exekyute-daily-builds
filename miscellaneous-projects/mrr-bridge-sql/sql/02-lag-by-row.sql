-- The bridge built the quick way, with LAG over the rows the log holds.
-- Opening and closing are the month totals and are right. The movements are
-- not: LAG looks back one row, not one month, so a customer who comes back
-- after skipping months is compared with the last month they paid, and reads
-- as expansion or contraction on that old amount, or as nothing at all if
-- the amount is the same. A customer who stops paying has no row in the month
-- they leave, so churn never shows. Whatever the movements fail to explain
-- lands in the last column.
WITH RECURSIVE
bounds AS (
    SELECT MIN(n) AS first_no, MAX(n) AS last_no
    FROM (
        SELECT CAST(substr(month, 1, 4) AS INTEGER) * 12 + CAST(substr(month, 6, 2) AS INTEGER) - 1 AS n
        FROM mrr
    )
),
-- Every month from the first in the log to the last, counted as years times
-- twelve plus the month counted from zero, so a month nobody paid for still
-- gets a total.
months(n) AS (
    SELECT first_no FROM bounds
    UNION ALL
    SELECT n + 1 FROM months WHERE n < (SELECT last_no FROM bounds)
),
calendar AS (
    SELECT n, printf('%04d-%02d', n / 12, n % 12 + 1) AS month FROM months
),
totals AS (
    SELECT c.n, c.month, COALESCE(SUM(r.mrr_cents), 0) AS cents
    FROM calendar c
    LEFT JOIN mrr r ON r.month = c.month
    GROUP BY c.n, c.month
),
walk AS (
    SELECT n, month, LAG(cents) OVER (ORDER BY n) AS opening, cents AS closing
    FROM totals
),
lagged AS (
    SELECT
        month,
        mrr_cents AS cents,
        LAG(mrr_cents) OVER (PARTITION BY customer ORDER BY month) AS prev
    FROM mrr
),
moves AS (
    SELECT
        month,
        SUM(CASE WHEN prev IS NULL THEN cents ELSE 0 END) AS new,
        SUM(CASE WHEN cents > prev THEN cents - prev ELSE 0 END) AS expansion,
        SUM(CASE WHEN cents < prev THEN cents - prev ELSE 0 END) AS contraction
    FROM lagged
    GROUP BY month
),
bridge AS (
    SELECT
        w.n,
        w.month,
        w.opening,
        COALESCE(m.new, 0) AS new,
        COALESCE(m.expansion, 0) AS expansion,
        COALESCE(m.contraction, 0) AS contraction,
        w.closing
    FROM walk w
    LEFT JOIN moves m ON m.month = w.month
    WHERE w.opening IS NOT NULL
)
SELECT
    month,
    printf('%.2f', opening / 100.0) AS opening,
    printf('%.2f', new / 100.0) AS new,
    printf('%.2f', expansion / 100.0) AS expansion,
    printf('%.2f', contraction / 100.0) AS contraction,
    printf('%.2f', closing / 100.0) AS closing,
    printf('%.2f', (closing - opening - new - expansion - contraction) / 100.0) AS unexplained
FROM bridge
ORDER BY n;
