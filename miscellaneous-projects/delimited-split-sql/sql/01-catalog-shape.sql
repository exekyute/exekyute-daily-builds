-- The catalog at a glance, counted without splitting anything. A list of n
-- tags holds n - 1 commas, so the length the commas take up gives the tag
-- count directly: the string minus itself with the commas removed, plus
-- one. It is a useful shortcut and a fragile one, since it counts every
-- comma-separated slot as a tag, and a leading, doubled, or trailing comma,
-- or a slot holding only whitespace, each adds a tag that is not there.
--
-- A field holding nothing but whitespace counts as untagged, using the same
-- set of characters query 03 trims. Query 03 splits the lists properly, and
-- the test suite checks the two totals agree on this catalog, which has none
-- of the cases that break the shortcut.
SELECT COUNT(*) AS products,
       SUM(trim(tags, ' ' || char(9) || char(160)) <> '') AS tagged,
       SUM(trim(tags, ' ' || char(9) || char(160)) = '') AS untagged,
       SUM(CASE WHEN trim(tags, ' ' || char(9) || char(160)) = '' THEN 0
                ELSE length(tags) - length(replace(tags, ',', '')) + 1 END) AS tag_mentions,
       MAX(CASE WHEN trim(tags, ' ' || char(9) || char(160)) = '' THEN 0
                ELSE length(tags) - length(replace(tags, ',', '')) + 1 END) AS most_tags_on_one
FROM products;
