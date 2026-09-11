-- The split, one row per tag. SQLite has no function that breaks a string
-- apart, so a recursive CTE walks it instead. The seed row appends a comma
-- so every tag, including the last, ends in one. Each step cuts off the
-- text up to the next comma with instr and substr, keeps the remainder,
-- and recurses on it until nothing is left.
--
-- Each piece is trimmed, since a list typed as "white, infrared" leaves a
-- leading space on every tag after the first. SQLite's trim() removes only
-- the plain space unless told otherwise, so it is handed a set that also
-- covers the tab and the non-breaking space text pasted from a web page or
-- a word processor carries. Each piece is then lowercased, since a tag is
-- a vocabulary word and "Red" and "red" mean the same thing.
--
-- A piece that trims to nothing, from a leading, doubled, or trailing comma
-- or a slot holding only whitespace, is dropped. Position is the piece's
-- place in the list as typed, so a leading or doubled comma leaves a gap
-- in the numbering, while a trailing one drops the last slot and leaves
-- none. An empty tag list never enters the recursion at all.
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
SELECT p.product_id,
       pr.name,
       p.position,
       lower(trim(p.piece, ' ' || char(9) || char(160))) AS tag
FROM pieces p
JOIN products pr ON pr.product_id = p.product_id
WHERE p.position > 0
  AND trim(p.piece, ' ' || char(9) || char(160)) <> ''
ORDER BY p.product_id, p.position;
