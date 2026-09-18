-- The explosion: every raw part one unit of each product takes. The same
-- walk as query 02 with UNION ALL, which keeps every row, so a part reached
-- by two routes is counted once for each. The quantity is multiplied at
-- every step down: two wheels of 32 spokes each is 64 spokes.
--
-- level counts the steps down from the product. It also caps the walk: a
-- route can pass through at most as many lines as the bill has, so a level
-- past that would mean a loop. The loader refuses loops before any query
-- runs, and the cap keeps a loop that got past it from running forever.
--
-- routes is how many ways the part is reached, and deepest is the lowest
-- level it turns up at.
WITH RECURSIVE exploded(product, part, qty, level) AS (
    SELECT parent, child, qty, 1
    FROM bom
    WHERE parent NOT IN (SELECT child FROM bom)
    UNION ALL
    SELECT e.product, b.child, e.qty * b.qty, e.level + 1
    FROM exploded e
    JOIN bom b ON b.parent = e.part
    WHERE e.level < (SELECT COUNT(*) FROM bom)
)
SELECT product,
       part,
       SUM(qty) AS per_unit,
       COUNT(*) AS routes,
       MAX(level) AS deepest
FROM exploded
WHERE part NOT IN (SELECT parent FROM bom)
GROUP BY product, part
ORDER BY product, part;
