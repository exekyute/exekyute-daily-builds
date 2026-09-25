-- Week by week, all-store growth next to comparable-store growth. A week runs
-- Sunday to Saturday and is keyed by the date of its Sunday, so the week
-- that holds 31 December and 1 January stays one week; a key made from the
-- year and a week number would split it. The report covers every whole
-- week of the log whose same week 52 weeks earlier is inside the log too.
--
-- Each day is set against the day 364 days earlier, the same weekday. The
-- all-store columns count every store open on either day. The comp columns
-- count a store on a day only when it was open on both, and comp_days counts
-- those store-days.
WITH RECURSIVE
bounds AS (
    SELECT
        date(MIN(sale_date), '+364 days', 'weekday 0') AS first_day,
        date(MAX(sale_date), '-6 days', 'weekday 6') AS last_day
    FROM sales
),
weeks(week_start) AS (
    SELECT first_day FROM bounds WHERE first_day <= last_day
    UNION ALL
    SELECT date(week_start, '+7 days') FROM weeks WHERE week_start < date((SELECT last_day FROM bounds), '-6 days')
),
pairs AS (
    SELECT n.sale_date AS day, n.sales_cents AS now_cents, b.sales_cents AS then_cents
    FROM sales n
    JOIN bounds ON n.sale_date BETWEEN bounds.first_day AND bounds.last_day
    LEFT JOIN sales b ON b.store = n.store AND b.sale_date = date(n.sale_date, '-364 days')
    UNION ALL
    SELECT date(b.sale_date, '+364 days'), NULL, b.sales_cents
    FROM sales b
    JOIN bounds ON b.sale_date BETWEEN date(bounds.first_day, '-364 days') AND date(bounds.last_day, '-364 days')
    WHERE NOT EXISTS (
        SELECT 1 FROM sales n WHERE n.store = b.store AND n.sale_date = date(b.sale_date, '+364 days')
    )
),
weekly AS (
    SELECT
        -- The Sunday on or before the day.
        date(day, '-6 days', 'weekday 0') AS week_start,
        SUM(COALESCE(now_cents, 0)) AS now_cents,
        SUM(COALESCE(then_cents, 0)) AS then_cents,
        SUM(now_cents IS NOT NULL AND then_cents IS NOT NULL) AS comp_days,
        SUM(CASE WHEN now_cents IS NOT NULL AND then_cents IS NOT NULL THEN now_cents ELSE 0 END) AS comp_now,
        SUM(CASE WHEN now_cents IS NOT NULL AND then_cents IS NOT NULL THEN then_cents ELSE 0 END) AS comp_then
    FROM pairs
    GROUP BY date(day, '-6 days', 'weekday 0')
),
kinds(is_total) AS (
    SELECT 0 UNION ALL SELECT 1
),
grouped AS (
    SELECT
        k.is_total,
        CASE WHEN k.is_total = 0 THEN w.week_start END AS week_start,
        SUM(COALESCE(x.now_cents, 0)) AS now_cents,
        SUM(COALESCE(x.then_cents, 0)) AS then_cents,
        SUM(COALESCE(x.comp_days, 0)) AS comp_days,
        SUM(COALESCE(x.comp_now, 0)) AS comp_now,
        SUM(COALESCE(x.comp_then, 0)) AS comp_then
    FROM weeks w
    LEFT JOIN weekly x ON x.week_start = w.week_start
    CROSS JOIN kinds k
    GROUP BY k.is_total, CASE WHEN k.is_total = 0 THEN w.week_start END
),
rated AS (
    SELECT
        *,
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
    CASE WHEN is_total = 1 THEN 'total' ELSE week_start || ' to ' || date(week_start, '+6 days') END AS week,
    printf('%.2f', now_cents / 100.0) AS sales,
    printf('%.2f', then_cents / 100.0) AS last_year,
    CASE WHEN all_tenths IS NOT NULL
         THEN printf('%s%d.%d', CASE WHEN all_tenths < 0 THEN '-' WHEN all_tenths > 0 THEN '+' ELSE '' END,
                     abs(all_tenths) / 10, abs(all_tenths) % 10)
    END AS all_stores_pct,
    comp_days,
    printf('%.2f', comp_now / 100.0) AS comp_sales,
    printf('%.2f', comp_then / 100.0) AS comp_last_year,
    CASE WHEN comp_tenths IS NOT NULL
         THEN printf('%s%d.%d', CASE WHEN comp_tenths < 0 THEN '-' WHEN comp_tenths > 0 THEN '+' ELSE '' END,
                     abs(comp_tenths) / 10, abs(comp_tenths) % 10)
    END AS comp_pct
FROM rated
ORDER BY is_total, week_start;
