-- The easy way to split a bill: work out each department's share of the
-- amount by weight, and round that share to the nearest cent on its own.
-- Every share is as close to exact as a cent allows, and the shares can
-- still fail to add up to the bill. ROUND takes a half cent up.
WITH totals AS (
    SELECT bill_id, SUM(weight) AS total_weight
    FROM splits
    GROUP BY bill_id
),
rounded AS (
    SELECT s.bill_id,
           CAST(ROUND(b.amount_cents * s.weight * 1.0 / t.total_weight) AS INTEGER) AS share_cents
    FROM splits s
    JOIN bills b ON b.bill_id = s.bill_id
    JOIN totals t ON t.bill_id = s.bill_id
)
SELECT b.bill_id,
       b.bill,
       printf('%d.%02d', b.amount_cents / 100, b.amount_cents % 100) AS amount,
       COUNT(*) AS departments,
       printf('%d.%02d', SUM(r.share_cents) / 100, SUM(r.share_cents) % 100) AS rounded_total,
       SUM(r.share_cents) - b.amount_cents AS off_by_cents
FROM bills b
JOIN rounded r ON r.bill_id = b.bill_id
GROUP BY b.bill_id, b.bill, b.amount_cents
ORDER BY b.bill_id;
