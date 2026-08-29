-- What was charged to each category itself, before any rollup. The LEFT JOIN
-- keeps pure structure nodes like Facilities in the list at 0.00, and spend
-- recorded directly on a mid-level node like Utilities shows up here as its
-- own line rather than disappearing under the children.
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
)
SELECT t.path,
       COUNT(e.expense_id) AS expenses,
       printf('%.2f', COALESCE(SUM(e.cents), 0) / 100.0) AS direct_total
FROM tree t
LEFT JOIN expenses e ON e.category_id = t.category_id
GROUP BY t.category_id, t.path, t.sort_path
ORDER BY t.sort_path;
