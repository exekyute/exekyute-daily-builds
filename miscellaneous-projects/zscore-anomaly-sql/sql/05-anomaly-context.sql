-- Each flagged day beside the range its baseline allowed: the two-sigma band
-- around the trailing mean, and how far outside it the day landed. This is
-- the line an incident note quotes. A flat-baseline day has no band to
-- quote, so its columns say so instead of faking one.
WITH baselined AS (
    SELECT metric_date,
           orders,
           COUNT(*) OVER w AS window_days,
           AVG(orders) OVER w AS mean_prev,
           sqrt(MAX(0.0, AVG(orders * orders) OVER w
                - AVG(orders) OVER w * AVG(orders) OVER w)) AS sigma_prev
    FROM daily_metrics
    WINDOW w AS (ORDER BY metric_date ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING)
)
SELECT metric_date,
       orders,
       CASE WHEN sigma_prev = 0 THEN 'no band: baseline never moved'
            ELSE printf('%.1f to %.1f', mean_prev - 2 * sigma_prev, mean_prev + 2 * sigma_prev)
       END AS allowed_band,
       CASE WHEN sigma_prev = 0 THEN ''
            WHEN orders > mean_prev + 2 * sigma_prev
                THEN printf('%.1f above the band', orders - (mean_prev + 2 * sigma_prev))
            ELSE printf('%.1f below the band', (mean_prev - 2 * sigma_prev) - orders)
       END AS exceedance
FROM baselined
WHERE window_days = 14
  AND (sigma_prev = 0 OR ABS((orders - mean_prev) / sigma_prev) >= 2)
ORDER BY metric_date;
