-- Each conversion's revenue credited to channels three ways, using only the
-- touches that count toward it, as query 03 draws the window:
--
--     first_touch  the whole revenue to the channel of the earliest touch
--     last_touch   the whole revenue to the channel of the latest touch
--     linear       the revenue shared by touch, so a channel with two of
--                  four touches earns half
--
-- Touches made in the same minute are taken in touch_id order, as in 03.
--
-- Linear is split to the cent by largest remainder. Each channel first gets
-- revenue * touches / in_window cut down to the whole cent, in whole-number
-- arithmetic, and revenue * touches % in_window is the part cut off, in
-- in_window-ths of a cent. The parts cut off add up to exactly the cents
-- left over, and each is less than a cent, so fewer cents are left over
-- than there are channels. They go one each to the channels that lost the
-- most in the cut, and a tie goes to the channel whose name sorts first.
-- So every model's credit adds back to the conversion's revenue exactly.
--
-- A conversion with no touch in its window is listed once, as
-- (unattributed), with its whole revenue under every model.
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
    -- Only the touches in the window join; a conversion with none keeps one
    -- row with no touch in it.
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
    -- An unattributed conversion's one row, with no touch in it, is both
    -- first and last in its own partition, so first and last touch already
    -- hand it the whole revenue. Linear divides by in_window, which is 0
    -- there, and SQLite gives NULL for that, so linear hands it the revenue
    -- by name.
    SELECT conversion_id,
           revenue_cents,
           COALESCE(channel, '(unattributed)') AS channel,
           touches,
           in_window,
           revenue_cents * is_first AS first_cents,
           revenue_cents * is_last AS last_cents,
           CASE WHEN in_window = 0 THEN revenue_cents ELSE floor_cents + (place <= leftover) END AS linear_cents
    FROM placed
)
SELECT conversion_id AS conversion,
       printf('%d.%02d', revenue_cents / 100, revenue_cents % 100) AS revenue,
       channel,
       touches,
       in_window,
       printf('%d.%02d', first_cents / 100, first_cents % 100) AS first_touch,
       printf('%d.%02d', last_cents / 100, last_cents % 100) AS last_touch,
       printf('%d.%02d', linear_cents / 100, linear_cents % 100) AS linear
FROM credited
ORDER BY conversion_id, channel;
