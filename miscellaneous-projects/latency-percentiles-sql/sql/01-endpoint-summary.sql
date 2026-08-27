-- The numbers a naive dashboard shows: request counts and the mean. The mean
-- is the setup for everything after it: two slow outliers put the search
-- average above 133 ms while half of all search requests finish in 80 ms or
-- less.
SELECT endpoint,
       COUNT(*) AS requests,
       MIN(duration_ms) AS min_ms,
       ROUND(AVG(duration_ms), 2) AS mean_ms,
       MAX(duration_ms) AS max_ms
FROM requests
GROUP BY endpoint
ORDER BY endpoint;
