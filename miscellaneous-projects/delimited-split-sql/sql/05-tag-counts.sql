-- What the split makes possible: a count per tag. A LIKE can count products
-- for a tag it is handed, as query 04 does, but it has no way to find out
-- which tags exist; the split produces that list, and once the tags are
-- rows they group like any other column.
--
-- The spellings column counts the distinct forms each tag arrived in after
-- trimming, so a tag typed two ways shows as two. Here red was typed both
-- "red" and "Red", and lowercasing is what folded them into one count.
WITH RECURSIVE pieces(product_id, position, piece, rest) AS (
    SELECT product_id, 0, NULL, tags || ','
    FROM products
    WHERE tags <> ''
    UNION ALL
    SELECT product_id,
           position + 1,
           substr(rest, 1, instr(rest, ',') - 1),
           substr(rest, instr(rest, ',') + 1)
    FROM pieces
    WHERE rest <> ''
)
SELECT lower(trim(piece, ' ' || char(9) || char(160))) AS tag,
       COUNT(DISTINCT product_id) AS products,
       COUNT(DISTINCT trim(piece, ' ' || char(9) || char(160))) AS spellings
FROM pieces
WHERE position > 0
  AND trim(piece, ' ' || char(9) || char(160)) <> ''
GROUP BY lower(trim(piece, ' ' || char(9) || char(160)))
ORDER BY products DESC, tag;
