-- Each month's fiscal year-to-date against last fiscal year's, to the same
-- fiscal month, and the growth between them, from the second fiscal year in
-- the log on. The calendar growth from query 02 sits in the last column for
-- comparison. Every month has a line here, missing ones included, so the
-- line twelve back is always the same month a year before; twelve rows back
-- in the log itself lands too far back, or on no row at all, wherever a
-- missing month falls in between. A total that is unknown because of a
-- missing month leaves the growth that leans on it blank. Growth is to a
-- whole percent, worked out in whole numbers with a half rounded away from
-- zero, and left blank where last year's total is unknown or zero.
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
months(n, start_no, last_no) AS (
    SELECT start_no, start_no, last_no FROM bounds
    UNION ALL
    SELECT n + 1, start_no, last_no FROM months WHERE n < last_no
),
spine AS (
    SELECT
        n,
        start_no,
        printf('%04d-%02d', n / 12, n % 12 + 1) AS month,
        (n - 3) / 12 AS fy,
        (n - 3) % 12 + 1 AS fm
    FROM months
),
filled AS (
    SELECT s.n, s.start_no, s.month, s.fy, s.fm, r.revenue_cents AS cents
    FROM spine s
    LEFT JOIN revenue r ON r.month = s.month
),
ytd AS (
    SELECT
        n,
        start_no,
        month,
        fy,
        fm,
        CASE WHEN COUNT(*) OVER (PARTITION BY fy ORDER BY n ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                  = COUNT(cents) OVER (PARTITION BY fy ORDER BY n ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             THEN SUM(cents) OVER (PARTITION BY fy ORDER BY n ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        END AS fiscal_ytd,
        -- The calendar running total as query 02 has it, on the months the
        -- log holds.
        CASE WHEN cents IS NOT NULL
             THEN SUM(cents) OVER (PARTITION BY n / 12 ORDER BY n ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        END AS calendar_ytd
    FROM filled
),
compared AS (
    SELECT
        n,
        start_no,
        month,
        fy,
        fm,
        fiscal_ytd,
        LAG(fiscal_ytd, 12) OVER (ORDER BY n) AS last_year_ytd,
        calendar_ytd,
        LAG(calendar_ytd, 12) OVER (ORDER BY n) AS calendar_last_year
    FROM ytd
)
SELECT
    month,
    CASE WHEN (fy + 1) % 100 = 0 THEN printf('%d-%d', fy, fy + 1)
         ELSE printf('%d-%02d', fy, (fy + 1) % 100) END AS fiscal_year,
    fm AS fiscal_month,
    CASE WHEN fiscal_ytd IS NOT NULL THEN printf('%d.%02d', fiscal_ytd / 100, fiscal_ytd % 100) END AS fiscal_ytd,
    CASE WHEN last_year_ytd IS NOT NULL
         THEN printf('%d.%02d', last_year_ytd / 100, last_year_ytd % 100) END AS last_year_ytd,
    CASE WHEN last_year_ytd > 0 AND fiscal_ytd IS NOT NULL THEN
        CASE WHEN fiscal_ytd >= last_year_ytd
             THEN (200 * (fiscal_ytd - last_year_ytd) + last_year_ytd) / (2 * last_year_ytd)
             ELSE -((200 * (last_year_ytd - fiscal_ytd) + last_year_ytd) / (2 * last_year_ytd)) END
    END AS growth_pct,
    CASE WHEN calendar_last_year > 0 AND calendar_ytd IS NOT NULL THEN
        CASE WHEN calendar_ytd >= calendar_last_year
             THEN (200 * (calendar_ytd - calendar_last_year) + calendar_last_year) / (2 * calendar_last_year)
             ELSE -((200 * (calendar_last_year - calendar_ytd) + calendar_last_year) / (2 * calendar_last_year)) END
    END AS calendar_growth_pct
FROM compared
WHERE n >= start_no + 12
ORDER BY n;
