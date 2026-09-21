-- The choice the log cannot make: what a missing day counts as. Read as a
-- day of zero sales, the seven-day average is the frame's sum over seven,
-- and every missing day pulls it down. Read as a day whose sales are
-- unknown, it is the sum over the days logged, and a missing day drops out.
-- A shop shut for the day sold nothing, so zero is right for it; a day left
-- out of the export could have sold anything, so unknown is right for that
-- one. The log shows both the same way, as no row. The frame is RANGE over whole day
-- numbers, as in query 03. A day less than six days after the first one has
-- a window reaching back before the log began, which neither reading can
-- fill, so it is flagged as partial. Both averages round half up to a whole cent
-- in whole numbers.
WITH numbered AS (
    SELECT day, sales_cents, CAST(julianday(day) AS INTEGER) AS day_no FROM daily_sales
),
windowed AS (
    SELECT
        day,
        day_no,
        MIN(day_no) OVER () AS first_no,
        COUNT(*) OVER seven_days AS days_logged,
        SUM(sales_cents) OVER seven_days AS window_cents
    FROM numbered
    WINDOW seven_days AS (ORDER BY day_no RANGE BETWEEN 6 PRECEDING AND CURRENT ROW)
),
averaged AS (
    SELECT
        day,
        day_no,
        first_no,
        days_logged,
        (2 * window_cents + 7) / 14 AS as_zero,
        (2 * window_cents + days_logged) / (2 * days_logged) AS as_unknown
    FROM windowed
)
SELECT
    day,
    days_logged,
    printf('%d.%02d', as_zero / 100, as_zero % 100) AS as_zero,
    printf('%d.%02d', as_unknown / 100, as_unknown % 100) AS as_unknown,
    printf('%d.%02d', (as_unknown - as_zero) / 100, (as_unknown - as_zero) % 100) AS gap,
    CASE WHEN day_no - 6 < first_no THEN 'partial: the window starts before the log' ELSE '' END AS note
FROM averaged
ORDER BY day;
