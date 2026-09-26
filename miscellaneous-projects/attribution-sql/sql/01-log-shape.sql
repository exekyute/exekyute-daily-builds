-- The two logs at a glance: how many touches, across how many channels and
-- customers, and how many conversions, by how many customers, for how much
-- revenue. Revenue is held in whole cents and printed as a decimal here.
SELECT
    (SELECT COUNT(*) FROM touches) AS touches,
    (SELECT COUNT(DISTINCT channel) FROM touches) AS channels,
    (SELECT COUNT(DISTINCT customer) FROM touches) AS customers_touched,
    (SELECT COUNT(*) FROM conversions) AS conversions,
    (SELECT COUNT(DISTINCT customer) FROM conversions) AS customers_converting,
    (SELECT printf('%d.%02d', SUM(revenue_cents) / 100, SUM(revenue_cents) % 100) FROM conversions) AS revenue;
