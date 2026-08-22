-- Three integrity checks on the hand-maintained price list, the kind of table
-- where ranges drift apart because people edit them by hand. Overlaps come
-- from a self-join on the same product, with rowid as a tie-break so two rows
-- that start on the same day still pair up. Gaps compare each row's start to
-- the furthest end of every earlier row for that product, a running MAX, so a
-- short row nested inside a longer one cannot fake a gap. The last check
-- counts open-ended rows, of which a product should have at most one. An
-- empty result means the list is clean.
WITH ranges AS (
    SELECT rowid AS rid,
           product,
           valid_from,
           valid_to,
           COALESCE(valid_to, '9999-12-31') AS valid_until
    FROM price_list
),
overlaps AS (
    SELECT a.product,
           'overlap' AS issue,
           'rows starting ' || a.valid_from || ' and ' || b.valid_from || ' overlap' AS detail
    FROM ranges a
    JOIN ranges b
      ON b.product = a.product
     AND (b.valid_from > a.valid_from OR (b.valid_from = a.valid_from AND b.rid > a.rid))
     AND b.valid_from <= a.valid_until
),
gaps AS (
    SELECT product,
           'gap' AS issue,
           DATE(covered_through, '+1 day') || ' to ' || DATE(valid_from, '-1 day') || ' uncovered' AS detail
    FROM (
        SELECT product,
               valid_from,
               MAX(valid_until) OVER (
                   PARTITION BY product ORDER BY valid_from, rid
                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
               ) AS covered_through
        FROM ranges
    )
    WHERE covered_through IS NOT NULL
      AND covered_through < DATE(valid_from, '-1 day')
),
multi_current AS (
    SELECT product,
           'multiple current rows' AS issue,
           COUNT(*) || ' rows with no valid_to' AS detail
    FROM price_list
    WHERE valid_to IS NULL
    GROUP BY product
    HAVING COUNT(*) > 1
)
SELECT product, issue, detail FROM overlaps
UNION ALL
SELECT product, issue, detail FROM gaps
UNION ALL
SELECT product, issue, detail FROM multi_current
ORDER BY product, issue, detail;
