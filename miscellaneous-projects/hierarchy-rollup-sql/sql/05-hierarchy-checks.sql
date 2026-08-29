-- Integrity checks against the draft hierarchy, the kind of table where hand
-- edits break structure: a category parented to itself, a parent id that
-- exists nowhere, and a loop where following parents comes back to the start.
-- The cycle walk climbs each category's ancestor chain and flags anyone whose
-- chain returns to them; the hop cap is the table's own row count, enough to
-- traverse any cycle the table could hold while still refusing to walk
-- forever. An empty result means the draft is safe to promote.
WITH RECURSIVE selfp AS (
    SELECT category_id
    FROM draft_categories
    WHERE parent_id = category_id
),
orphans AS (
    SELECT category_id, parent_id
    FROM draft_categories
    WHERE parent_id IS NOT NULL
      AND parent_id NOT IN (SELECT category_id FROM draft_categories)
),
up(start_id, current_id, hops) AS (
    SELECT category_id, parent_id, 1
    FROM draft_categories
    WHERE parent_id IS NOT NULL AND parent_id <> category_id
    UNION ALL
    SELECT u.start_id, d.parent_id, u.hops + 1
    FROM up u
    JOIN draft_categories d ON d.category_id = u.current_id
    WHERE d.parent_id IS NOT NULL
      AND u.current_id <> u.start_id
      AND u.hops <= (SELECT COUNT(*) FROM draft_categories)
),
cycles AS (
    SELECT DISTINCT start_id
    FROM up
    WHERE current_id = start_id
)
SELECT 'cycle' AS issue, start_id AS category_id,
       'following parents comes back to it' AS detail
FROM cycles
UNION ALL
SELECT 'self-parent', category_id, 'points at itself'
FROM selfp
UNION ALL
SELECT 'unknown parent', category_id, 'parent ' || parent_id || ' does not exist'
FROM orphans
ORDER BY issue, category_id;
