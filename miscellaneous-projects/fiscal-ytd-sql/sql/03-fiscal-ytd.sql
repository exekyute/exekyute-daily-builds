-- Year-to-date on the fiscal year, which runs from April to March. Every
-- month gets a line, from the April that opens the first fiscal year in the
-- log to the last month in the log, so a month with no row still shows. A
-- month is counted as years times twelve plus the month counted from zero;
-- three months off that, divided by twelve, is the calendar year the fiscal
-- year starts in, and the remainder plus one is the fiscal month, 1 for April
-- and 12 for March. The running total starts again at each fiscal month 1.
-- A month missing from the log is unknown, not zero: a month with no revenue
-- is written as 0.00. From a missing month to the end of its fiscal year the
-- total is left blank, and the last column names the first month missing.
WITH RECURSIVE
bounds AS (
    SELECT first_no - (first_no - 3) % 12 AS start_no, last_no
    FROM (
        SELECT
            CAST(substr(MIN(month), 1, 4) AS INTEGER) * 12 + CAST(substr(MIN(month), 6, 2) AS INTEGER) - 1 AS first_no,
            CAST(substr(MAX(month), 1, 4) AS INTEGER) * 12 + CAST(substr(MAX(month), 6, 2) AS INTEGER) - 1 AS last_no
        FROM revenue
    )
),
months(n, last_no) AS (
    SELECT start_no, last_no FROM bounds
    UNION ALL
    SELECT n + 1, last_no FROM months WHERE n < last_no
),
spine AS (
    SELECT
        n,
        printf('%04d-%02d', n / 12, n % 12 + 1) AS month,
        (n - 3) / 12 AS fy,
        (n - 3) % 12 + 1 AS fm
    FROM months
),
filled AS (
    SELECT s.n, s.month, s.fy, s.fm, r.revenue_cents AS cents
    FROM spine s
    LEFT JOIN revenue r ON r.month = s.month
),
ytd AS (
    SELECT
        n,
        month,
        fy,
        fm,
        cents,
        CASE WHEN COUNT(*) OVER (PARTITION BY fy ORDER BY n ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                  = COUNT(cents) OVER (PARTITION BY fy ORDER BY n ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             THEN SUM(cents) OVER (PARTITION BY fy ORDER BY n ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        END AS fiscal_ytd,
        MIN(CASE WHEN cents IS NULL THEN n END)
            OVER (PARTITION BY fy ORDER BY n ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS gap_no
    FROM filled
)
SELECT
    month,
    CASE WHEN (fy + 1) % 100 = 0 THEN printf('%d-%d', fy, fy + 1)
         ELSE printf('%d-%02d', fy, (fy + 1) % 100) END AS fiscal_year,
    fm AS fiscal_month,
    CASE WHEN cents IS NOT NULL THEN printf('%d.%02d', cents / 100, cents % 100) END AS revenue,
    CASE WHEN fiscal_ytd IS NOT NULL THEN printf('%d.%02d', fiscal_ytd / 100, fiscal_ytd % 100) END AS fiscal_ytd,
    CASE WHEN gap_no IS NOT NULL THEN printf('%04d-%02d', gap_no / 12, gap_no % 12 + 1) END AS unknown_from
FROM ytd
ORDER BY n;
