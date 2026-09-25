-- Comparable-store sales, store by store. Each day of the report weeks is set
-- against the day 364 days earlier, the same weekday 52 weeks back. A store
-- counts on a day only when it traded on both days. A store that had not
-- opened 52 weeks earlier stays out until it has, and a day a store was shut
-- takes the day 52 weeks away from it out with it, whichever year the
-- closure fell in.
--
-- pairs holds every store and report day with the store open on either
-- side: the days open now, with the same store 52 weeks earlier where it was
-- open, and the days open 52 weeks earlier with no day now. SQLite before
-- 3.39 has no FULL OUTER JOIN, so it is a LEFT JOIN one way and a NOT EXISTS
-- the other, joined by UNION ALL. When the log has a report week, one empty
-- row goes in as well, so the total line still prints when no store traded
-- on either side; it adds nothing to any sum or count.
WITH
bounds AS (
    SELECT
        date(MIN(sale_date), '+364 days', 'weekday 0') AS first_day,
        date(MAX(sale_date), '-6 days', 'weekday 6') AS last_day
    FROM sales
),
pairs AS (
    SELECT n.store, n.sales_cents AS now_cents, b.sales_cents AS then_cents
    FROM sales n
    JOIN bounds ON n.sale_date BETWEEN bounds.first_day AND bounds.last_day
    LEFT JOIN sales b ON b.store = n.store AND b.sale_date = date(n.sale_date, '-364 days')
    UNION ALL
    SELECT b.store, NULL, b.sales_cents
    FROM sales b
    JOIN bounds ON b.sale_date BETWEEN date(bounds.first_day, '-364 days') AND date(bounds.last_day, '-364 days')
    WHERE NOT EXISTS (
        SELECT 1 FROM sales n WHERE n.store = b.store AND n.sale_date = date(b.sale_date, '+364 days')
    )
    UNION ALL
    SELECT NULL, NULL, NULL FROM bounds WHERE first_day <= last_day
),
kinds(is_total) AS (
    SELECT 0 UNION ALL SELECT 1
),
grouped AS (
    SELECT
        k.is_total,
        CASE WHEN k.is_total = 0 THEN p.store END AS store,
        SUM(p.now_cents IS NOT NULL) AS days_open,
        SUM(p.then_cents IS NOT NULL) AS open_year_before,
        SUM(p.now_cents IS NOT NULL AND p.then_cents IS NOT NULL) AS comp_days,
        SUM(COALESCE(p.now_cents, 0)) AS sales,
        SUM(CASE WHEN p.now_cents IS NOT NULL AND p.then_cents IS NOT NULL THEN p.now_cents ELSE 0 END) AS comp_now,
        SUM(CASE WHEN p.now_cents IS NOT NULL AND p.then_cents IS NOT NULL THEN p.then_cents ELSE 0 END) AS comp_then
    FROM pairs p
    CROSS JOIN kinds k
    GROUP BY k.is_total, CASE WHEN k.is_total = 0 THEN p.store END
    HAVING k.is_total = 1 OR COUNT(p.store) > 0
),
rated AS (
    SELECT
        *,
        CASE WHEN comp_then > 0
             THEN (2000 * (comp_now - comp_then) + CASE WHEN comp_now < comp_then THEN -comp_then
                                                        ELSE comp_then END) / (2 * comp_then)
        END AS tenths
    FROM grouped
)
SELECT
    CASE WHEN is_total = 1 THEN 'all stores' ELSE store END AS store,
    days_open,
    open_year_before,
    comp_days,
    printf('%.2f', sales / 100.0) AS sales,
    printf('%.2f', comp_now / 100.0) AS comp_sales,
    printf('%.2f', comp_then / 100.0) AS comp_last_year,
    CASE WHEN tenths IS NOT NULL
         THEN printf('%s%d.%d', CASE WHEN tenths < 0 THEN '-' WHEN tenths > 0 THEN '+' ELSE '' END,
                     abs(tenths) / 10, abs(tenths) % 10)
    END AS comp_pct
FROM rated
ORDER BY is_total, store;
