-- Each month in customers and in rates. Paying at open, less those lost,
-- plus those won (new or back again), gives paying at close. Gross revenue
-- retention is the opening MRR kept after contraction and churn; net revenue
-- retention adds expansion back. Neither counts new customers or
-- reactivations. Rates are to a tenth of a percent, rounded half up in whole
-- numbers, and left blank for a month that opens with nobody paying.
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
monthly AS (
    SELECT
        n,
        month,
        SUM(CASE WHEN prev > 0 THEN 1 ELSE 0 END) AS paying_at_open,
        SUM(CASE WHEN movement = 'churn' THEN 1 ELSE 0 END) AS lost,
        SUM(CASE WHEN movement IN ('new', 'reactivation') THEN 1 ELSE 0 END) AS won,
        SUM(CASE WHEN cents > 0 THEN 1 ELSE 0 END) AS paying_at_close,
        SUM(prev) AS opening,
        SUM(CASE WHEN movement IN ('contraction', 'churn') THEN change ELSE 0 END) AS lost_cents,
        SUM(CASE WHEN movement = 'expansion' THEN change ELSE 0 END) AS expansion_cents
    FROM classified
    GROUP BY n, month
),
rates AS (
    SELECT
        n,
        month,
        paying_at_open,
        lost,
        won,
        paying_at_close,
        CASE WHEN opening > 0
             THEN (2000 * (opening + lost_cents) + opening) / (2 * opening) END AS grr_tenths,
        CASE WHEN opening > 0
             THEN (2000 * (opening + lost_cents + expansion_cents) + opening) / (2 * opening) END AS nrr_tenths
    FROM monthly
)
SELECT
    month,
    paying_at_open,
    lost,
    won,
    paying_at_close,
    CASE WHEN grr_tenths IS NOT NULL THEN printf('%d.%d', grr_tenths / 10, grr_tenths % 10) END AS grr_pct,
    CASE WHEN nrr_tenths IS NOT NULL THEN printf('%d.%d', nrr_tenths / 10, nrr_tenths % 10) END AS nrr_pct
FROM rates
ORDER BY n;
