-- The log at a glance: its first and last month, how many months it holds,
-- how many are missing and how many are a real zero, the first and last
-- fiscal year it touches, and how far into the last one it runs. A fiscal
-- year runs from April to March and is named for the two calendar years it
-- spans: 2025-26 runs from April 2025 to March 2026. Months are counted as
-- years times twelve plus the month counted from zero, so taking three off
-- puts April at the start of a count of twelve, and dividing by twelve gives
-- the calendar year in which the fiscal year starts. A month is missing when
-- it has no row between the April that opens the first fiscal year and the
-- last month in the log, so months before the log starts in its first
-- fiscal year count as missing too.
SELECT
    first_month,
    last_month,
    logged,
    last_no - (first_no - (first_no - 3) % 12) + 1 - logged AS missing,
    at_zero,
    CASE WHEN (first_fy + 1) % 100 = 0 THEN printf('%d-%d', first_fy, first_fy + 1)
         ELSE printf('%d-%02d', first_fy, (first_fy + 1) % 100) END AS first_fiscal_year,
    CASE WHEN (last_fy + 1) % 100 = 0 THEN printf('%d-%d', last_fy, last_fy + 1)
         ELSE printf('%d-%02d', last_fy, (last_fy + 1) % 100) END AS last_fiscal_year,
    (last_no - 3) % 12 + 1 AS last_fiscal_month
FROM (
    SELECT
        first_month,
        last_month,
        logged,
        at_zero,
        first_no,
        last_no,
        (first_no - 3) / 12 AS first_fy,
        (last_no - 3) / 12 AS last_fy
    FROM (
        SELECT
            MIN(month) AS first_month,
            MAX(month) AS last_month,
            COUNT(*) AS logged,
            SUM(revenue_cents = 0) AS at_zero,
            CAST(substr(MIN(month), 1, 4) AS INTEGER) * 12 + CAST(substr(MIN(month), 6, 2) AS INTEGER) - 1 AS first_no,
            CAST(substr(MAX(month), 1, 4) AS INTEGER) * 12 + CAST(substr(MAX(month), 6, 2) AS INTEGER) - 1 AS last_no
        FROM revenue
    )
);
