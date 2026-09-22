-- One line per fiscal year: the month it runs to, how many of its months
-- have passed and how many of those are missing, its revenue to date, the
-- same months of the fiscal year before, and the growth between them. A
-- year still running is set only against the same months last year; the
-- whole of last year sits in the last column and plays no part in the
-- growth. Revenue is left blank for a year with a month missing, and so is
-- any figure that leans on it. Growth is to a whole percent, worked out in
-- whole numbers with a half rounded away from zero, and left blank where
-- last year's figure is unknown or zero.
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
        last_no,
        printf('%04d-%02d', n / 12, n % 12 + 1) AS month,
        (n - 3) / 12 AS fy,
        (n - 3) % 12 + 1 AS fm
    FROM months
),
filled AS (
    SELECT s.n, s.last_no, s.month, s.fy, s.fm, r.revenue_cents AS cents
    FROM spine s
    LEFT JOIN revenue r ON r.month = s.month
),
ytd AS (
    SELECT
        n,
        last_no,
        month,
        fy,
        fm,
        cents,
        CASE WHEN COUNT(*) OVER (PARTITION BY fy ORDER BY n ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                  = COUNT(cents) OVER (PARTITION BY fy ORDER BY n ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             THEN SUM(cents) OVER (PARTITION BY fy ORDER BY n ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        END AS fiscal_ytd
    FROM filled
),
compared AS (
    SELECT
        n,
        last_no,
        month,
        fy,
        fm,
        cents,
        -- Every month has a line, so twelve back is the same fiscal month
        -- a year before.
        LAG(fiscal_ytd, 12) OVER (ORDER BY n) AS last_year_ytd
    FROM ytd
),
years AS (
    -- One chain ending in a single GROUP BY, with the whole of last year
    -- taken by a window over the years themselves.
    SELECT
        fy,
        MAX(month) AS through,
        COUNT(*) AS months,
        COUNT(*) - COUNT(cents) AS missing,
        CASE WHEN COUNT(*) = COUNT(cents) THEN SUM(cents) END AS revenue,
        -- The year's last line, month 12 or the last month in the log,
        -- carries last year's total to the same fiscal month.
        MAX(CASE WHEN fm = 12 OR n = last_no THEN last_year_ytd END) AS same_months,
        LAG(CASE WHEN COUNT(*) = COUNT(cents) THEN SUM(cents) END) OVER (ORDER BY fy) AS full_year
    FROM compared
    GROUP BY fy
)
SELECT
    CASE WHEN (fy + 1) % 100 = 0 THEN printf('%d-%d', fy, fy + 1)
         ELSE printf('%d-%02d', fy, (fy + 1) % 100) END AS fiscal_year,
    through,
    months,
    missing,
    CASE WHEN revenue IS NOT NULL THEN printf('%d.%02d', revenue / 100, revenue % 100) END AS revenue,
    CASE WHEN same_months IS NOT NULL
         THEN printf('%d.%02d', same_months / 100, same_months % 100) END AS same_months_last_year,
    CASE WHEN same_months > 0 AND revenue IS NOT NULL THEN
        CASE WHEN revenue >= same_months THEN (200 * (revenue - same_months) + same_months) / (2 * same_months)
             ELSE -((200 * (same_months - revenue) + same_months) / (2 * same_months)) END
    END AS growth_pct,
    CASE WHEN full_year IS NOT NULL THEN printf('%d.%02d', full_year / 100, full_year % 100) END AS full_year_last_year
FROM years
ORDER BY fy;
