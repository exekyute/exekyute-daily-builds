-- The seven-day average the tempting way: average each day with the six
-- rows before it, a frame of ROWS BETWEEN 6 PRECEDING AND CURRENT ROW. ROWS
-- counts rows, not days. When one of the seven days is missing and the log
-- goes back further, the seven rows reach past the week, and the average
-- takes in sales from outside the week it claims to cover. window_from is the earliest day
-- the frame reached and calendar_days how many days that is from the current
-- one, counting both. The average itself is the frame's sum over its row
-- count, rounded half up to a whole cent in whole numbers; only the frame is
-- wrong.
WITH windowed AS (
    SELECT
        day,
        sales_cents,
        MIN(day) OVER last_seven_rows AS window_from,
        SUM(sales_cents) OVER last_seven_rows AS window_cents,
        COUNT(*) OVER last_seven_rows AS rows_used
    FROM daily_sales
    WINDOW last_seven_rows AS (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
)
SELECT
    day,
    printf('%d.%02d', sales_cents / 100, sales_cents % 100) AS sales,
    window_from,
    CAST(julianday(day) - julianday(window_from) AS INTEGER) + 1 AS calendar_days,
    printf('%d.%02d', (2 * window_cents + rows_used) / (2 * rows_used) / 100,
                      (2 * window_cents + rows_used) / (2 * rows_used) % 100) AS avg_7
FROM windowed
ORDER BY day;
