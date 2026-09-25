-- The log at a glance, one line per store: its first and last day, the days
-- it traded, and the days between the two with no row. A store has a row
-- for every day it was open, so a store that opened partway through starts
-- late, and one that shut for a while shows the days it was shut.
SELECT
    store,
    MIN(sale_date) AS first_day,
    MAX(sale_date) AS last_day,
    COUNT(*) AS days_open,
    CAST(julianday(MAX(sale_date)) - julianday(MIN(sale_date)) AS INTEGER) + 1 - COUNT(*) AS days_closed
FROM sales
GROUP BY store
ORDER BY store;
