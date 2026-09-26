-- Channel totals under the three models of query 04, with the join from
-- query 02 beside them, and the lines that show whether each adds up:
--
--     (unattributed)   revenue from conversions with no touch in the window
--     (total)          every line above it added together
--     (over revenue)   the total less the revenue in the conversions log
--
-- Under each model every conversion's revenue goes out once, to channels or
-- to (unattributed), so its total is the revenue and it is over by 0.00.
-- The join has no figure on the (unattributed) line, since a conversion with
-- no touches drops out of it. It is over by what it counts more than once,
-- less what it drops, so it can come in under the revenue as well.
--
-- Every channel in the touch log gets a line, even one that no model and no
-- join credits. The credit is built exactly as in query 04; the join's column
-- is query 02's credited total.
WITH conv AS (
    SELECT conversion_id,
           customer,
           converted_at,
           revenue_cents,
           LAG(converted_at) OVER (PARTITION BY customer ORDER BY converted_at) AS previous,
           strftime('%Y-%m-%d %H:%M', converted_at, '-30 days') AS lookback_from
    FROM conversions
),
counted AS (
    SELECT c.conversion_id,
           c.revenue_cents,
           t.touch_id,
           t.channel,
           t.touched_at
    FROM conv c
    LEFT JOIN touches t
           ON t.customer = c.customer
          AND t.touched_at <= c.converted_at
          AND t.touched_at >= c.lookback_from
          AND (c.previous IS NULL OR t.touched_at > c.previous)
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY conversion_id ORDER BY touched_at, touch_id) AS from_first,
           ROW_NUMBER() OVER (PARTITION BY conversion_id ORDER BY touched_at DESC, touch_id DESC) AS from_last,
           COUNT(touch_id) OVER (PARTITION BY conversion_id) AS in_window
    FROM counted
),
by_channel AS (
    SELECT conversion_id,
           channel,
           MAX(revenue_cents) AS revenue_cents,
           MAX(in_window) AS in_window,
           COUNT(touch_id) AS touches,
           MAX(from_first = 1) AS is_first,
           MAX(from_last = 1) AS is_last
    FROM ranked
    GROUP BY conversion_id, channel
),
cut AS (
    SELECT *,
           revenue_cents * touches / in_window AS floor_cents,
           revenue_cents * touches % in_window AS remainder
    FROM by_channel
),
placed AS (
    SELECT *,
           revenue_cents - SUM(floor_cents) OVER (PARTITION BY conversion_id) AS leftover,
           ROW_NUMBER() OVER (PARTITION BY conversion_id ORDER BY remainder DESC, channel) AS place
    FROM cut
),
credited AS (
    SELECT channel,
           revenue_cents * is_first AS first_cents,
           revenue_cents * is_last AS last_cents,
           CASE WHEN in_window = 0 THEN revenue_cents ELSE floor_cents + (place <= leftover) END AS linear_cents
    FROM placed
),
joined AS (
    SELECT t.channel,
           SUM(c.revenue_cents) AS naive_cents
    FROM touches t
    JOIN conversions c ON c.customer = t.customer
    GROUP BY t.channel
),
entries AS (
    -- One source of rows for every line. A credit row with no channel is an
    -- unattributed conversion. The join's figure is blank on the credit
    -- rows, so the (unattributed) line has no join figure, and the row of
    -- zeros with no channel keeps that line in place when every conversion
    -- is attributed.
    SELECT channel, first_cents, last_cents, linear_cents, NULL AS naive_cents
    FROM credited
    UNION ALL
    SELECT NULL, 0, 0, 0, NULL
    UNION ALL
    SELECT channel, 0, 0, 0, naive_cents
    FROM joined
    UNION ALL
    SELECT DISTINCT channel, 0, 0, 0, 0
    FROM touches
),
lines AS (
    SELECT channel,
           SUM(first_cents) AS first_cents,
           SUM(last_cents) AS last_cents,
           SUM(linear_cents) AS linear_cents,
           SUM(naive_cents) AS naive_cents
    FROM entries
    GROUP BY channel
),
summed AS (
    -- Each line carries the sum of all the lines, and one line, the first,
    -- is marked to carry the two total lines below.
    SELECT *,
           SUM(first_cents) OVER () AS all_first,
           SUM(last_cents) OVER () AS all_last,
           SUM(linear_cents) OVER () AS all_linear,
           SUM(naive_cents) OVER () AS all_naive,
           ROW_NUMBER() OVER (ORDER BY channel) AS nth
    FROM lines
),
kinds(kind) AS (
    VALUES (0), (1), (2)
),
totals AS (
    -- kind 0 is a line's own figures, kind 1 the total, kind 2 the total
    -- less the revenue in the conversions log.
    SELECT CASE k.kind WHEN 0 THEN (s.channel IS NULL) ELSE k.kind + 1 END AS sort_key,
           CASE k.kind WHEN 0 THEN COALESCE(s.channel, '(unattributed)')
                       WHEN 1 THEN '(total)'
                       ELSE '(over revenue)' END AS line,
           CASE k.kind WHEN 0 THEN s.first_cents WHEN 1 THEN s.all_first
                       ELSE s.all_first - r.revenue_cents END AS first_cents,
           CASE k.kind WHEN 0 THEN s.last_cents WHEN 1 THEN s.all_last
                       ELSE s.all_last - r.revenue_cents END AS last_cents,
           CASE k.kind WHEN 0 THEN s.linear_cents WHEN 1 THEN s.all_linear
                       ELSE s.all_linear - r.revenue_cents END AS linear_cents,
           CASE k.kind WHEN 0 THEN s.naive_cents WHEN 1 THEN s.all_naive
                       ELSE s.all_naive - r.revenue_cents END AS naive_cents
    FROM summed s
    CROSS JOIN kinds k
    CROSS JOIN (SELECT SUM(revenue_cents) AS revenue_cents FROM conversions) r
    WHERE k.kind = 0 OR s.nth = 1
)
-- The three models are never blank and never below zero. The join's figure
-- is blank on the (unattributed) line, which printf would print as 0.00, and
-- below zero when it comes in under the revenue, so it keeps its sign.
SELECT line,
       printf('%d.%02d', first_cents / 100, first_cents % 100) AS first_touch,
       printf('%d.%02d', last_cents / 100, last_cents % 100) AS last_touch,
       printf('%d.%02d', linear_cents / 100, linear_cents % 100) AS linear,
       CASE WHEN naive_cents IS NULL THEN NULL
            ELSE CASE WHEN naive_cents < 0 THEN '-' ELSE '' END
                 || printf('%d.%02d', abs(naive_cents) / 100, abs(naive_cents) % 100) END AS naive_join
FROM totals
ORDER BY sort_key, line;
