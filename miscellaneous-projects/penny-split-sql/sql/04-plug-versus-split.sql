-- The usual fix for rounded shares that miss the bill is a plug: round every
-- share, then add whatever the rounding missed by to the largest share, the
-- one with the largest weight, or the name that sorts first when two
-- weights are equal. The plug balances the bill, but it puts the whole
-- difference on one department. When rounding missed, that department ends
-- up a cent or more away from what it owes, unless rounding missed by a
-- single cent and the plug takes back the rounding on that very share.
--
-- For each bill, this sets the plug beside the largest remainder split from
-- query 03: how far rounding missed, where the plug went, how far each
-- method's shares miss the bill, and for each method the furthest any
-- department's share ends up from its exact share.
-- The misses are in cents, cut (not rounded) to three decimal places, so a
-- miss under a cent never prints as 1.000.
WITH totals AS (
    SELECT bill_id, SUM(weight) AS total_weight
    FROM splits
    GROUP BY bill_id
),
shares AS (
    SELECT s.bill_id,
           s.department,
           s.weight,
           b.amount_cents,
           t.total_weight,
           CAST(ROUND(b.amount_cents * s.weight * 1.0 / t.total_weight) AS INTEGER) AS rounded_cents,
           b.amount_cents * s.weight / t.total_weight AS floor_cents,
           b.amount_cents * s.weight % t.total_weight AS remainder
    FROM splits s
    JOIN bills b ON b.bill_id = s.bill_id
    JOIN totals t ON t.bill_id = s.bill_id
),
placed AS (
    SELECT *,
           amount_cents - SUM(rounded_cents) OVER (PARTITION BY bill_id) AS rounding_gap,
           ROW_NUMBER() OVER (PARTITION BY bill_id ORDER BY weight DESC, department) AS size_place,
           amount_cents - SUM(floor_cents) OVER (PARTITION BY bill_id) AS leftover,
           ROW_NUMBER() OVER (PARTITION BY bill_id ORDER BY remainder DESC, department) AS place
    FROM shares
),
allocated AS (
    SELECT bill_id,
           department,
           weight,
           amount_cents,
           total_weight,
           rounded_cents,
           rounding_gap,
           size_place,
           rounded_cents + CASE WHEN size_place = 1 THEN rounding_gap ELSE 0 END AS plugged_cents,
           floor_cents + CASE WHEN place <= leftover THEN 1 ELSE 0 END AS split_cents
    FROM placed
),
per_bill AS (
    SELECT bill_id,
           SUM(rounded_cents) - MAX(amount_cents) AS rounded_off_by,
           MAX(CASE WHEN size_place = 1 AND rounding_gap <> 0 THEN department END) AS plugged_into,
           SUM(plugged_cents) - MAX(amount_cents) AS plug_off_by,
           MAX(ABS(plugged_cents * total_weight - amount_cents * weight)) * 1000
               / MAX(total_weight) AS plug_miss,
           SUM(split_cents) - MAX(amount_cents) AS split_off_by,
           MAX(ABS(split_cents * total_weight - amount_cents * weight)) * 1000
               / MAX(total_weight) AS split_miss
    FROM allocated
    GROUP BY bill_id
)
SELECT p.bill_id,
       b.bill,
       p.rounded_off_by,
       p.plugged_into,
       p.plug_off_by,
       printf('%d.%03d', p.plug_miss / 1000, p.plug_miss % 1000) AS plug_worst_miss,
       p.split_off_by,
       printf('%d.%03d', p.split_miss / 1000, p.split_miss % 1000) AS split_worst_miss
FROM per_bill p
JOIN bills b ON b.bill_id = p.bill_id
ORDER BY p.bill_id;
