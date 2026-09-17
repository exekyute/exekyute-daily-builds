-- Largest remainder: give every department its share cut down to the whole
-- cent, which can leave the bill a few cents short, then hand those cents out
-- one each, starting with the departments whose shares lost the most in
-- the cut.
--
-- In whole numbers, amount_cents * weight / total_weight is the share cut
-- down to the cent, and amount_cents * weight % total_weight is the part
-- that was cut off, counted in total_weight-ths of a cent. The parts cut
-- off add up to exactly the cents left over, and each one is less than a
-- whole cent, so there are fewer cents left over than departments and no
-- department gets more than one.
--
-- The remainders are compared as whole numbers. Worked out in floating
-- point, two shares cut by the same fraction of a cent can come out a
-- hair apart and hand the cent to the wrong department. When two
-- remainders are equal, the cent goes to the department whose name sorts
-- first.
WITH totals AS (
    SELECT bill_id, SUM(weight) AS total_weight
    FROM splits
    GROUP BY bill_id
),
cut AS (
    SELECT s.bill_id,
           s.department,
           s.weight,
           b.amount_cents,
           t.total_weight,
           b.amount_cents * s.weight / t.total_weight AS floor_cents,
           b.amount_cents * s.weight % t.total_weight AS remainder
    FROM splits s
    JOIN bills b ON b.bill_id = s.bill_id
    JOIN totals t ON t.bill_id = s.bill_id
),
placed AS (
    SELECT bill_id,
           department,
           weight,
           total_weight,
           floor_cents,
           remainder,
           amount_cents - SUM(floor_cents) OVER (PARTITION BY bill_id) AS leftover,
           ROW_NUMBER() OVER (PARTITION BY bill_id ORDER BY remainder DESC, department) AS place
    FROM cut
),
shared AS (
    SELECT *,
           CASE WHEN place <= leftover THEN 1 ELSE 0 END AS extra_cent
    FROM placed
)
SELECT bill_id,
       department,
       weight,
       printf('%d.%02d', floor_cents / 100, floor_cents % 100) AS floored,
       remainder || '/' || total_weight AS remainder,
       place,
       extra_cent,
       printf('%d.%02d', (floor_cents + extra_cent) / 100, (floor_cents + extra_cent) % 100) AS share
FROM shared
ORDER BY bill_id, department;
