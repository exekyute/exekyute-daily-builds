-- Three ways to ask whether a product carries a tag, run for every tag the
-- catalog uses. The substring LIKE from query 02 finds the word anywhere.
-- The padded LIKE wraps the list and the tag in commas first, so ',red,'
-- can only match a whole element, which cures the substring problem. The
-- split from query 03 compares whole trimmed tags.
--
-- The two shortcuts go wrong in opposite directions, for any tag free of
-- the LIKE wildcards % and _. The substring version can only over-match,
-- since every product that carries a tag also holds it as a substring.
-- The padded version can only under-match, since it needs an element that
-- is exactly the tag, and an element typed with a space after the comma
-- never is. On this catalog that costs it three tags.
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
),
tagged AS (
    SELECT DISTINCT product_id, lower(trim(piece, ' ' || char(9) || char(160))) AS tag
    FROM pieces
    WHERE position > 0
      AND trim(piece, ' ' || char(9) || char(160)) <> ''
),
counts AS (
    SELECT v.tag,
           (SELECT COUNT(*) FROM tagged t WHERE t.tag = v.tag) AS by_split,
           (SELECT COUNT(*) FROM products p
            WHERE ',' || p.tags || ',' LIKE '%,' || v.tag || ',%') AS by_padded_like,
           (SELECT COUNT(*) FROM products p
            WHERE p.tags LIKE '%' || v.tag || '%') AS by_substring_like
    FROM (SELECT DISTINCT tag FROM tagged) v
)
SELECT tag,
       by_split,
       by_padded_like,
       by_substring_like,
       CASE WHEN by_padded_like = by_split AND by_substring_like = by_split THEN 'agree'
            WHEN by_padded_like < by_split AND by_substring_like > by_split THEN 'both off'
            WHEN by_substring_like > by_split THEN 'substring over-matches'
            ELSE 'padded under-matches' END AS verdict
FROM counts
ORDER BY tag;
