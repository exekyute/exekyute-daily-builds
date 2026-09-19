-- The bridge: each month's opening MRR, the five movements, and the closing
-- MRR. Every change a customer makes falls under exactly one movement, so
-- opening plus the movements comes to closing, and the last column checks
-- that it does. The total line runs from the first month's opening to the
-- last month's closing. It is built in the same pass as the monthly lines,
-- by reading each month twice, once for its own line and once for the total,
-- because SQLite before 3.35 works a CTE out again every time it is named.
WITH RECURSIVE
bounds AS (
    SELECT MIN(n) AS first_no, MAX(n) AS last_no
    FROM (
        SELECT CAST(substr(month, 1, 4) AS INTEGER) * 12 + CAST(substr(month, 6, 2) AS INTEGER) - 1 AS n
        FROM mrr
    )
),
months(n) AS (
    SELECT first_no FROM bounds
    UNION ALL
    SELECT n + 1 FROM months WHERE n < (SELECT last_no FROM bounds)
),
calendar AS (
    SELECT n, printf('%04d-%02d', n / 12, n % 12 + 1) AS month FROM months
),
customers AS (
    SELECT DISTINCT customer FROM mrr
),
grid AS (
    SELECT c.n, c.month, k.customer, COALESCE(r.mrr_cents, 0) AS cents
    FROM calendar c
    CROSS JOIN customers k
    LEFT JOIN mrr r ON r.month = c.month AND r.customer = k.customer
),
compared AS (
    SELECT
        n,
        month,
        customer,
        cents,
        LAG(cents) OVER (PARTITION BY customer ORDER BY n) AS prev,
        MAX(cents) OVER (PARTITION BY customer ORDER BY n
                         ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS most_before
    FROM grid
),
classified AS (
    SELECT
        n,
        month,
        prev,
        cents,
        cents - prev AS change,
        CASE
            WHEN cents = prev THEN NULL
            WHEN prev = 0 AND most_before > 0 THEN 'reactivation'
            WHEN prev = 0 THEN 'new'
            WHEN cents = 0 THEN 'churn'
            WHEN cents > prev THEN 'expansion'
            ELSE 'contraction'
        END AS movement
    FROM compared
    WHERE prev IS NOT NULL
),
bridge AS (
    SELECT
        n,
        month,
        SUM(prev) AS opening,
        SUM(CASE WHEN movement = 'new' THEN change ELSE 0 END) AS new,
        SUM(CASE WHEN movement = 'reactivation' THEN change ELSE 0 END) AS reactivation,
        SUM(CASE WHEN movement = 'expansion' THEN change ELSE 0 END) AS expansion,
        SUM(CASE WHEN movement = 'contraction' THEN change ELSE 0 END) AS contraction,
        SUM(CASE WHEN movement = 'churn' THEN change ELSE 0 END) AS churn,
        SUM(cents) AS closing
    FROM classified
    GROUP BY n, month
),
kinds(is_total) AS (
    SELECT 0 UNION ALL SELECT 1
),
report AS (
    SELECT
        k.is_total,
        CASE WHEN k.is_total = 0 THEN b.n END AS n,
        MAX(CASE WHEN k.is_total = 0 THEN b.month ELSE 'total' END) AS month,
        SUM(CASE WHEN k.is_total = 0 OR b.n = (SELECT first_no + 1 FROM bounds) THEN b.opening ELSE 0 END) AS opening,
        SUM(b.new) AS new,
        SUM(b.reactivation) AS reactivation,
        SUM(b.expansion) AS expansion,
        SUM(b.contraction) AS contraction,
        SUM(b.churn) AS churn,
        SUM(CASE WHEN k.is_total = 0 OR b.n = (SELECT last_no FROM bounds) THEN b.closing ELSE 0 END) AS closing
    FROM bridge b
    CROSS JOIN kinds k
    GROUP BY k.is_total, CASE WHEN k.is_total = 0 THEN b.n END
)
SELECT
    month,
    printf('%.2f', opening / 100.0) AS opening,
    printf('%.2f', new / 100.0) AS new,
    printf('%.2f', reactivation / 100.0) AS reactivation,
    printf('%.2f', expansion / 100.0) AS expansion,
    printf('%.2f', contraction / 100.0) AS contraction,
    printf('%.2f', churn / 100.0) AS churn,
    printf('%.2f', closing / 100.0) AS closing,
    CASE WHEN opening + new + reactivation + expansion + contraction + churn = closing
         THEN 'yes' ELSE 'no' END AS adds_up
FROM report
ORDER BY is_total, n;
