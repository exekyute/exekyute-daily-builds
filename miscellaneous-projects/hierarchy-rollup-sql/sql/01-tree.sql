-- The tree walked from its roots: every category with its depth and the full
-- ancestor path. The anchor picks rows with no parent; each step hangs the
-- children under whatever the previous step produced. Ordering uses a second
-- copy of the path joined with char(31), which sorts below every printable
-- character, so children stay right after their parent even when a sibling's
-- name extends another's, something the display separator cannot promise.
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
SELECT category_id, depth, path
FROM tree
ORDER BY sort_path;
