-- Two proofs that the rollup holds together: the root subtrees re-sum to the
-- grand total of every expense, and each parent's subtree equals its own
-- spend plus its children's subtrees, checked in cents so equality is exact.
WITH RECURSIVE closure(ancestor_id, category_id, hops) AS (
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
),
subtree AS (
    SELECT cl.ancestor_id AS category_id, COALESCE(SUM(d.cents), 0) AS cents
    FROM closure cl
    LEFT JOIN direct d ON d.category_id = cl.category_id
    GROUP BY cl.ancestor_id
),
roots_total AS (
    SELECT SUM(s.cents) AS cents
    FROM subtree s
    JOIN categories c ON c.category_id = s.category_id
    WHERE c.parent_id IS NULL
),
grand AS (
    SELECT COALESCE(SUM(cents), 0) AS cents
    FROM expenses
),
violations AS (
    SELECT p.category_id
    FROM categories p
    JOIN subtree sp ON sp.category_id = p.category_id
    WHERE sp.cents <> COALESCE((SELECT SUM(sc.cents)
                                FROM categories ch
                                JOIN subtree sc ON sc.category_id = ch.category_id
                                WHERE ch.parent_id = p.category_id), 0)
                    + COALESCE((SELECT d.cents FROM direct d
                                WHERE d.category_id = p.category_id), 0)
)
SELECT 'root subtrees equal the grand total' AS check_name,
       printf('%.2f vs %.2f', r.cents / 100.0, g.cents / 100.0) AS detail,
       CASE WHEN r.cents = g.cents THEN 'ok' ELSE 'FAIL' END AS status
FROM roots_total r, grand g
UNION ALL
SELECT 'every parent equals its own spend plus its children',
       (SELECT COUNT(*) FROM violations) || ' violations',
       CASE WHEN (SELECT COUNT(*) FROM violations) = 0 THEN 'ok' ELSE 'FAIL' END;
