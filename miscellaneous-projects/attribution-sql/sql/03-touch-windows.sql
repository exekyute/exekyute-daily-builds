-- Which of a customer's touches each conversion may credit. A touch counts
-- toward a conversion when it falls in the 30 days before it and after the
-- customer's previous conversion:
--
--     lookback_from <= touched_at <= converted_at, and touched_at > previous
--
-- lookback_from is the conversion's own moment less 30 days, so a touch made
-- exactly 30 days before still counts and one a minute earlier does not. A
-- touch at the same moment as the conversion counts toward it, and a touch
-- at the same moment as the previous conversion belongs to that one, so no
-- touch counts toward two conversions.
--
-- Every other touch by the same customer is counted by why it was left out,
-- taking the first reason that fits: made after the conversion, made at or
-- before the previous conversion, or made more than 30 days before.
--
-- Timestamps are held as text in one form, 2026-04-15 14:00, so comparing
-- them as text compares them in time, and strftime writes lookback_from in
-- that same form. datetime() would add seconds, and '2026-03-16 14:00' sorts
-- before '2026-03-16 14:00:00', which would drop a touch made exactly 30
-- days before.
--
-- first_touch and last_touch are the channels of the earliest and the latest
-- touch that counts. Touches made in the same minute are taken in the order
-- they reached the log, by touch_id: of two at the same minute, the lower id
-- is the earlier one.
WITH conv AS (
    SELECT conversion_id,
           customer,
           converted_at,
           LAG(converted_at) OVER (PARTITION BY customer ORDER BY converted_at) AS previous,
           strftime('%Y-%m-%d %H:%M', converted_at, '-30 days') AS lookback_from
    FROM conversions
),
paired AS (
    -- A conversion with no touches at all still gets one row here, with no
    -- touch in it and no reason.
    SELECT c.conversion_id,
           c.customer,
           c.converted_at,
           c.previous,
           c.lookback_from,
           t.touch_id,
           t.channel,
           t.touched_at,
           CASE
               WHEN t.touch_id IS NULL THEN NULL
               WHEN t.touched_at > c.converted_at THEN 'after'
               WHEN t.touched_at <= c.previous THEN 'earlier'
               WHEN t.touched_at < c.lookback_from THEN 'too_old'
               ELSE 'in_window'
           END AS reason
    FROM conv c
    LEFT JOIN touches t ON t.customer = c.customer
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY conversion_id, reason ORDER BY touched_at, touch_id) AS from_first,
           ROW_NUMBER() OVER (PARTITION BY conversion_id, reason
                              ORDER BY touched_at DESC, touch_id DESC) AS from_last
    FROM paired
)
SELECT conversion_id AS conversion,
       customer,
       converted_at,
       previous,
       lookback_from,
       COUNT(CASE WHEN reason = 'in_window' THEN 1 END) AS in_window,
       COUNT(CASE WHEN reason = 'after' THEN 1 END) AS after,
       COUNT(CASE WHEN reason = 'earlier' THEN 1 END) AS earlier,
       COUNT(CASE WHEN reason = 'too_old' THEN 1 END) AS too_old,
       MAX(CASE WHEN reason = 'in_window' AND from_first = 1 THEN channel END) AS first_touch,
       MAX(CASE WHEN reason = 'in_window' AND from_last = 1 THEN channel END) AS last_touch
FROM ranked
GROUP BY conversion_id, customer, converted_at, previous, lookback_from
ORDER BY conversion_id;
