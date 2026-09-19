-- Every customer's change from one month to the next, named. The log only
-- holds the months a customer paid, so each customer is first given a row in
-- every month of the log, at zero where they paid nothing. With a row in
-- every month, LAG always finds the calendar month before. A customer going
-- from zero to paying is new, or a reactivation if they paid in any earlier
-- month of the log; paying to zero is churn; and a change while paying is
-- expansion or contraction.
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
        -- The most the customer paid in any month before this one.
        MAX(cents) OVER (PARTITION BY customer ORDER BY n
                         ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS most_before
    FROM grid
),
classified AS (
    SELECT
        n,
        month,
        customer,
        prev,
        cents,
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
)
SELECT
    month,
    customer,
    movement,
    printf('%.2f', prev / 100.0) AS mrr_before,
    printf('%.2f', cents / 100.0) AS mrr_after,
    printf('%.2f', (cents - prev) / 100.0) AS change
FROM classified
WHERE movement IS NOT NULL
ORDER BY n, customer;
