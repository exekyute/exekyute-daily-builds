-- Every category's subtree total: its own spend plus everything under it, to
-- any depth. The closure CTE builds (ancestor, descendant) pairs, seeded with
-- each category as its own descendant, so a node's subtree includes itself.
-- Joining expenses through the closure and grouping by ancestor is the whole
-- rollup. The hop guard is sized from the table itself, so no legitimate
-- depth ever truncates; the loader refuses a cyclic live tree at load, and
-- the checks in 05 are the same discipline for draft hierarchies.
WITH RECURSIVE tree(category_id, name, depth, path, sort_path) AS (
    SELECT category_id, name, 0, name, name
    FROM categories
    WHERE parent_id IS NULL
    UNION ALL
    SELECT c.category_id, c.name, t.depth + 1,
           t.path || ' > ' || c.name,
           t.sort_path || char(31) || c.name
    FROM categories c
    JOIN tree t ON t.category_id = c.parent_id
),
closure(ancestor_id, category_id, hops) AS (
    SELECT category_id, category_id, 0
    FROM categories
    UNION ALL
    SELECT cl.ancestor_id, c.category_id, cl.hops + 1
    FROM closure cl
    JOIN categories c ON c.parent_id = cl.category_id
    WHERE cl.hops < (SELECT COUNT(*) FROM categories)
),
direct AS (
    SELECT category_id, SUM(cents) AS cents
    FROM expenses
    GROUP BY category_id
)
SELECT t.path,
       printf('%.2f', COALESCE(own.cents, 0) / 100.0) AS direct_total,
       printf('%.2f', COALESCE(SUM(d.cents), 0) / 100.0) AS subtree_total
FROM tree t
JOIN closure cl ON cl.ancestor_id = t.category_id
LEFT JOIN direct d ON d.category_id = cl.category_id
LEFT JOIN direct own ON own.category_id = t.category_id
GROUP BY t.category_id, t.path, t.sort_path, own.cents
ORDER BY t.sort_path;
