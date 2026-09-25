-- The quick comparison: each day of the report weeks against the same date a
-- year earlier, every store counted, gathered by weekday. It goes wrong two
-- ways on an ordinary year and three across a leap day. The same date a year
-- earlier is 365 days back, or 366 across a leap day, so it is never the
-- same weekday: each Saturday is set against a Friday and each Sunday
-- against a Saturday, or a Thursday and a Friday across a leap day. A store
-- that was not open a year earlier adds sales on one side with nothing on
-- the other. And across a leap day date(day, '-1 year') sends both
-- 29 February and 1 March to the same 1 March, so one day counts twice.
--
-- The report weeks are the ones query 04 uses: Sunday to Saturday, each with
-- the same week 52 weeks earlier inside the log.
WITH RECURSIVE
bounds AS (
    SELECT
        date(MIN(sale_date), '+364 days', 'weekday 0') AS first_day,
        date(MAX(sale_date), '-6 days', 'weekday 6') AS last_day
    FROM sales
),
days(day) AS (
    SELECT first_day FROM bounds WHERE first_day <= last_day
    UNION ALL
    SELECT date(day, '+1 day') FROM days WHERE day < (SELECT last_day FROM bounds)
),
compared AS (
    SELECT
        CAST(strftime('%w', day) AS INTEGER) AS w,
        CAST(strftime('%w', date(day, '-1 year')) AS INTEGER) AS then_w,
        (SELECT COALESCE(SUM(sales_cents), 0) FROM sales WHERE sale_date = day) AS now_cents,
        (SELECT COALESCE(SUM(sales_cents), 0) FROM sales WHERE sale_date = date(day, '-1 year')) AS then_cents
    FROM days
),
kinds(is_total) AS (
    SELECT 0 UNION ALL SELECT 1
),
grouped AS (
    SELECT
        k.is_total,
        CASE WHEN k.is_total = 0 THEN c.w END AS w,
        CASE WHEN k.is_total = 0 THEN c.then_w END AS then_w,
        COUNT(*) AS days,
        SUM(c.now_cents) AS now_cents,
        SUM(c.then_cents) AS then_cents
    FROM compared c
    CROSS JOIN kinds k
    GROUP BY k.is_total, CASE WHEN k.is_total = 0 THEN c.w END, CASE WHEN k.is_total = 0 THEN c.then_w END
),
rated AS (
    SELECT
        *,
        -- Growth in tenths of a percent, worked out in whole numbers and
        -- rounded half away from zero; blank when a year earlier sold nothing.
        CASE WHEN then_cents > 0
             THEN (2000 * (now_cents - then_cents) + CASE WHEN now_cents < then_cents THEN -then_cents
                                                          ELSE then_cents END) / (2 * then_cents)
        END AS tenths
    FROM grouped
)
SELECT
    CASE WHEN is_total = 1 THEN 'all days' ELSE substr('SunMonTueWedThuFriSat', 3 * w + 1, 3) END AS weekday,
    CASE WHEN is_total = 0 THEN substr('SunMonTueWedThuFriSat', 3 * then_w + 1, 3) END AS compared_with,
    days,
    printf('%.2f', now_cents / 100.0) AS sales,
    printf('%.2f', then_cents / 100.0) AS same_date_last_year,
    CASE WHEN tenths IS NOT NULL
         THEN printf('%s%d.%d', CASE WHEN tenths < 0 THEN '-' WHEN tenths > 0 THEN '+' ELSE '' END,
                     abs(tenths) / 10, abs(tenths) % 10)
    END AS growth_pct
FROM rated
ORDER BY is_total, w, (w - then_w + 7) % 7;
