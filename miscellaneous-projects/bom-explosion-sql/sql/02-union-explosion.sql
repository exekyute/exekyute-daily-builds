-- The recursive query most people write first. Start from each product's
-- own lines, then keep joining the parts found so far back to the bill,
-- multiplying the quantity at each step, and add up the raw parts at the
-- bottom.
--
-- It is written with UNION, and UNION throws away a row that is already
-- there. Two different routes to the same part that arrive with the same
-- quantity make the same row, (product, part, qty), so one of them is
-- dropped. A city bike takes 4 bolts in its frame kit and 4 more in its fork
-- kit; UNION keeps one row of 4 and the bike comes out 4 bolts short. Two
-- routes that arrive with different quantities are kept, so the same query
-- is right about most parts and wrong about the ones that happen to repeat.
WITH RECURSIVE exploded(product, part, qty) AS (
    SELECT parent, child, qty
    FROM bom
    WHERE parent NOT IN (SELECT child FROM bom)
    UNION
    SELECT e.product, b.child, e.qty * b.qty
    FROM exploded e
    JOIN bom b ON b.parent = e.part
)
SELECT product,
       part,
       SUM(qty) AS per_unit
FROM exploded
WHERE part NOT IN (SELECT parent FROM bom)
GROUP BY product, part
ORDER BY product, part;
