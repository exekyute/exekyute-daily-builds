-- Growth by weekday over the report weeks, three ways: every store against
-- the same date a year earlier, as query 02 has it; every store against the
-- same weekday 52 weeks earlier; and comparable stores only, against the
-- same weekday. The first gap is the calendar, the second is the stores.
--
-- Matching the weekday gives up matching the date. A holiday on a fixed date
-- lands on a different weekday each year, so the same weekday 52 weeks
-- earlier can be an ordinary day set against a holiday, or the other way
-- round.
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
        (SELECT COALESCE(SUM(sales_cents), 0) FROM sales WHERE sale_date = day) AS now_cents,
        (SELECT COALESCE(SUM(sales_cents), 0) FROM sales WHERE sale_date = date(day, '-1 year')) AS same_date_cents,
        (SELECT COALESCE(SUM(sales_cents), 0) FROM sales WHERE sale_date = date(day, '-364 days')) AS then_cents,
        (SELECT COALESCE(SUM(n.sales_cents), 0)
         FROM sales n
         JOIN sales b ON b.store = n.store AND b.sale_date = date(day, '-364 days')
         WHERE n.sale_date = day) AS comp_now,
        (SELECT COALESCE(SUM(b.sales_cents), 0)
         FROM sales n
         JOIN sales b ON b.store = n.store AND b.sale_date = date(day, '-364 days')
         WHERE n.sale_date = day) AS comp_then
    FROM days
),
kinds(is_total) AS (
    SELECT 0 UNION ALL SELECT 1
),
grouped AS (
    SELECT
        k.is_total,
        CASE WHEN k.is_total = 0 THEN c.w END AS w,
        SUM(c.now_cents) AS now_cents,
        SUM(c.same_date_cents) AS same_date_cents,
        SUM(c.then_cents) AS then_cents,
        SUM(c.comp_now) AS comp_now,
        SUM(c.comp_then) AS comp_then
    FROM compared c
    CROSS JOIN kinds k
    GROUP BY k.is_total, CASE WHEN k.is_total = 0 THEN c.w END
),
rated AS (
    SELECT
        is_total,
        w,
        CASE WHEN same_date_cents > 0
             THEN (2000 * (now_cents - same_date_cents) + CASE WHEN now_cents < same_date_cents THEN -same_date_cents
                                                               ELSE same_date_cents END) / (2 * same_date_cents)
        END AS same_date_tenths,
        CASE WHEN then_cents > 0
             THEN (2000 * (now_cents - then_cents) + CASE WHEN now_cents < then_cents THEN -then_cents
                                                          ELSE then_cents END) / (2 * then_cents)
        END AS all_tenths,
        CASE WHEN comp_then > 0
             THEN (2000 * (comp_now - comp_then) + CASE WHEN comp_now < comp_then THEN -comp_then
                                                        ELSE comp_then END) / (2 * comp_then)
        END AS comp_tenths
    FROM grouped
)
SELECT
    CASE WHEN is_total = 1 THEN 'all days' ELSE substr('SunMonTueWedThuFriSat', 3 * w + 1, 3) END AS weekday,
    CASE WHEN same_date_tenths IS NOT NULL
         THEN printf('%s%d.%d', CASE WHEN same_date_tenths < 0 THEN '-' WHEN same_date_tenths > 0 THEN '+' ELSE '' END,
                     abs(same_date_tenths) / 10, abs(same_date_tenths) % 10)
    END AS same_date_all_stores,
    CASE WHEN all_tenths IS NOT NULL
         THEN printf('%s%d.%d', CASE WHEN all_tenths < 0 THEN '-' WHEN all_tenths > 0 THEN '+' ELSE '' END,
                     abs(all_tenths) / 10, abs(all_tenths) % 10)
    END AS same_weekday_all_stores,
    CASE WHEN comp_tenths IS NOT NULL
         THEN printf('%s%d.%d', CASE WHEN comp_tenths < 0 THEN '-' WHEN comp_tenths > 0 THEN '+' ELSE '' END,
                     abs(comp_tenths) / 10, abs(comp_tenths) % 10)
    END AS same_weekday_comp
FROM rated
ORDER BY is_total, w;
