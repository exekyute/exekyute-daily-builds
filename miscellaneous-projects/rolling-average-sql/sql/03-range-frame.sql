-- The seven-day average with a frame of seven calendar days. RANGE BETWEEN
-- 6 PRECEDING AND CURRENT ROW takes every row whose ORDER BY value runs from
-- six below the current row's up to it, so ordered by a whole day number it
-- holds the current day and the six before it, however many of them have a
-- row. The day number is julianday cut to a whole number. Ordered by the
-- date text instead, the query still runs, but SQLite cannot take six from
-- text: it leaves the offset off, and each day's frame holds only the rows
-- with the same date, which is the day alone. RANGE with a number before
-- PRECEDING needs SQLite 3.28 or newer. window_from is the first calendar
-- day of the frame, whether or not it has a row, and days_logged is how many
-- of the seven do. avg_7 averages the days logged, rounded half up to a
-- whole cent in whole numbers.
WITH numbered AS (
    SELECT day, sales_cents, CAST(julianday(day) AS INTEGER) AS day_no FROM daily_sales
),
windowed AS (
    SELECT
        day,
        sales_cents,
        COUNT(*) OVER seven_days AS days_logged,
        SUM(sales_cents) OVER seven_days AS window_cents
    FROM numbered
    WINDOW seven_days AS (ORDER BY day_no RANGE BETWEEN 6 PRECEDING AND CURRENT ROW)
)
SELECT
    day,
    printf('%d.%02d', sales_cents / 100, sales_cents % 100) AS sales,
    date(day, '-6 days') AS window_from,
    days_logged,
    printf('%d.%02d', window_cents / 100, window_cents % 100) AS window_sales,
    printf('%d.%02d', (2 * window_cents + days_logged) / (2 * days_logged) / 100,
                      (2 * window_cents + days_logged) / (2 * days_logged) % 100) AS avg_7
FROM windowed
ORDER BY day;
