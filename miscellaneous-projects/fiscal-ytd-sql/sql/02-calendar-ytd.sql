-- Year-to-date the calendar way: a running total that starts again every
-- January, beside last year's running total to the same calendar month and
-- the growth between them. It works on the rows the log holds, so a month
-- missing from the log has no line of its own and adds nothing to the
-- months after it. On a year that runs from April to March, January to March
-- report one to three months of a fiscal year that is ten to twelve months
-- old, and from April on the comparison still counts from January, so it
-- takes in January to March, the last three months of the fiscal year before.
-- Growth is to a whole percent, worked out in whole numbers with a half
-- rounded away from zero, and left blank where last year's total is missing
-- or zero.
WITH cal AS (
    SELECT
        month,
        CAST(substr(month, 1, 4) AS INTEGER) AS year,
        substr(month, 6, 2) AS mon,
        COUNT(*) OVER (PARTITION BY substr(month, 1, 4) ORDER BY month
                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS ytd_months,
        SUM(revenue_cents) OVER (PARTITION BY substr(month, 1, 4) ORDER BY month
                                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS ytd
    FROM revenue
),
paired AS (
    SELECT c.month, c.ytd_months, c.ytd, p.ytd AS prior
    FROM cal c
    LEFT JOIN cal p ON p.year = c.year - 1 AND p.mon = c.mon
)
SELECT
    month,
    ytd_months,
    printf('%d.%02d', ytd / 100, ytd % 100) AS calendar_ytd,
    CASE WHEN prior IS NOT NULL THEN printf('%d.%02d', prior / 100, prior % 100) END AS last_year_ytd,
    CASE WHEN prior > 0 THEN
        CASE WHEN ytd >= prior THEN (200 * (ytd - prior) + prior) / (2 * prior)
             ELSE -((200 * (prior - ytd) + prior) / (2 * prior)) END
    END AS growth_pct
FROM paired
ORDER BY month;
