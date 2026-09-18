-- How many of each item on the plan the shelf could build if that item had
-- the stock to itself: the raw part that runs out first sets the number,
-- and that part is the bottleneck. When two parts run out at the same
-- count, the bottleneck is the part code that sorts first.
--
-- Each item is measured alone. Items that share a part are not charged
-- against each other here, which is why query 04 can show a part running
-- short across the plan while every item on it could still be built alone.
WITH RECURSIVE exploded(item, part, qty, level) AS (
    SELECT o.item, b.child, b.qty, 1
    FROM orders o
    JOIN bom b ON b.parent = o.item
    UNION ALL
    SELECT e.item, b.child, e.qty * b.qty, e.level + 1
    FROM exploded e
    JOIN bom b ON b.parent = e.part
    WHERE e.level < (SELECT COUNT(*) FROM bom)
),
per_unit AS (
    SELECT item, part, SUM(qty) AS qty
    FROM exploded
    WHERE part NOT IN (SELECT parent FROM bom)
    GROUP BY item, part
),
limits AS (
    SELECT p.item,
           p.part,
           s.on_hand / p.qty AS can_build,
           ROW_NUMBER() OVER (PARTITION BY p.item ORDER BY s.on_hand / p.qty, p.part) AS place
    FROM per_unit p
    JOIN stock s ON s.part = p.part
)
SELECT o.item,
       o.qty AS ordered,
       l.can_build AS buildable,
       l.part AS bottleneck,
       MAX(o.qty - l.can_build, 0) AS short_units
FROM orders o
JOIN limits l ON l.item = o.item AND l.place = 1
ORDER BY o.item;
