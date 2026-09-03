-- Each day's trailing baseline: the mean and standard deviation of the 14
-- days BEFORE it, current day excluded, so a spike cannot dilute the very
-- baseline it is judged against. SQLite has no STDEV, so the deviation is
-- built from first principles: variance is the mean of the squares minus the
-- square of the mean, and sigma is its square root. The MAX clamp keeps a
-- float rounding error from handing sqrt a tiny negative variance.
SELECT metric_date,
       orders,
       COUNT(*) OVER w AS window_days,
       ROUND(AVG(orders) OVER w, 2) AS baseline_mean,
       ROUND(sqrt(MAX(0.0, AVG(orders * orders) OVER w
                  - AVG(orders) OVER w * AVG(orders) OVER w)), 2) AS baseline_sigma
FROM daily_metrics
WINDOW w AS (ORDER BY metric_date ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING)
ORDER BY metric_date;
