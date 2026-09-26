-- The tempting query: join every touch to every conversion by the same
-- customer and hand each touch's channel the revenue of every conversion it
-- is paired with.
--
-- Nothing in the join ties a touch to the conversion it could have led to.
-- A touch made after a conversion is paired with it. A customer's second
-- conversion is paired with the touches that came before the first, so
-- those touches are credited twice. A touch from months back counts as much
-- as one from the day before. And each conversion's revenue is counted once
-- for every touch it is paired with, so on a log like the sample, where most
-- conversions follow several touches, the channel totals come to far more
-- than the revenue there is. A conversion with no touches at all drops out
-- of the join and is reported nowhere, which pulls the total the other way.
SELECT channel,
       pairs,
       conversions,
       printf('%d.%02d', credited_cents / 100, credited_cents % 100) AS credited
FROM (
    SELECT 0 AS is_total,
           t.channel,
           COUNT(*) AS pairs,
           COUNT(DISTINCT c.conversion_id) AS conversions,
           SUM(c.revenue_cents) AS credited_cents
    FROM touches t
    JOIN conversions c ON c.customer = t.customer
    GROUP BY t.channel
    UNION ALL
    SELECT 1,
           '(total)',
           COUNT(*),
           COUNT(DISTINCT c.conversion_id),
           COALESCE(SUM(c.revenue_cents), 0)
    FROM touches t
    JOIN conversions c ON c.customer = t.customer
)
ORDER BY is_total, channel;
