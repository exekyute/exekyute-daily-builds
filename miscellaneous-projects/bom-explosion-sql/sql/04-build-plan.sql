-- What the week's build plan takes of each raw part, against what is on
-- the shelf. Each item on the plan is exploded as in query 03, the quantity
-- per unit is multiplied by the units ordered, and the parts are added up
-- across the plan. An item can be a product or a subassembly ordered on
-- its own, such as spare wheels.
--
-- union_need is what the same plan comes to if the walk is written with
-- UNION as in query 02, which drops a repeated route in each item it
-- explodes. short_by is what the plan needs beyond what is on hand.
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
union_walk(item, part, qty) AS (
    SELECT o.item, b.child, b.qty
    FROM orders o
    JOIN bom b ON b.parent = o.item
    UNION
    SELECT u.item, b.child, u.qty * b.qty
    FROM union_walk u
    JOIN bom b ON b.parent = u.part
),
needed AS (
    SELECT e.part, SUM(o.qty * e.qty) AS need
    FROM exploded e
    JOIN orders o ON o.item = e.item
    WHERE e.part NOT IN (SELECT parent FROM bom)
    GROUP BY e.part
),
union_needed AS (
    SELECT u.part, SUM(o.qty * u.qty) AS need
    FROM union_walk u
    JOIN orders o ON o.item = u.item
    WHERE u.part NOT IN (SELECT parent FROM bom)
    GROUP BY u.part
)
SELECT n.part,
       s.on_hand,
       n.need,
       MAX(n.need - s.on_hand, 0) AS short_by,
       un.need AS union_need
FROM needed n
JOIN stock s ON s.part = n.part
JOIN union_needed un ON un.part = n.part
ORDER BY n.part;
