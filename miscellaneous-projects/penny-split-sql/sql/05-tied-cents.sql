-- Where the leftover cents from query 03 went, department by department.
-- Some go on the size of the remainder. The rest are decided on a tie: a
-- department that got a cent lost the same fraction of a cent in the cut
-- as one that did not, and the only difference between them is which name
-- sorts first. On a bill split evenly that leaves cents over, every cent
-- is decided that way.
--
-- won_on_tie counts the cents a department got although a department that
-- missed out had the same remainder. lost_on_tie counts the times a
-- department missed out although a department that got a cent had the same
-- remainder. charged is the department's total across every bill.
WITH totals AS (
    SELECT bill_id, SUM(weight) AS total_weight
    FROM splits
    GROUP BY bill_id
),
cut AS (
    SELECT s.bill_id,
           s.department,
           b.amount_cents,
           b.amount_cents * s.weight / t.total_weight AS floor_cents,
           b.amount_cents * s.weight % t.total_weight AS remainder
    FROM splits s
    JOIN bills b ON b.bill_id = s.bill_id
    JOIN totals t ON t.bill_id = s.bill_id
),
placed AS (
    SELECT bill_id,
           department,
           floor_cents,
           remainder,
           amount_cents - SUM(floor_cents) OVER (PARTITION BY bill_id) AS leftover,
           ROW_NUMBER() OVER (PARTITION BY bill_id ORDER BY remainder DESC, department) AS place
    FROM cut
),
edges AS (
    SELECT *,
           MAX(CASE WHEN place = leftover THEN remainder END)
               OVER (PARTITION BY bill_id) AS last_in,
           MAX(CASE WHEN place = leftover + 1 THEN remainder END)
               OVER (PARTITION BY bill_id) AS first_out
    FROM placed
),
tallied AS (
    SELECT department,
           COUNT(*) AS bills,
           SUM(CASE WHEN place <= leftover THEN 1 ELSE 0 END) AS extra_cents,
           SUM(CASE WHEN place <= leftover AND remainder = first_out THEN 1 ELSE 0 END) AS won_on_tie,
           SUM(CASE WHEN place > leftover AND remainder = last_in THEN 1 ELSE 0 END) AS lost_on_tie,
           SUM(floor_cents + CASE WHEN place <= leftover THEN 1 ELSE 0 END) AS charged_cents
    FROM edges
    GROUP BY department
)
SELECT department,
       bills,
       extra_cents,
       won_on_tie,
       lost_on_tie,
       printf('%d.%02d', charged_cents / 100, charged_cents % 100) AS charged
FROM tallied
ORDER BY department;
