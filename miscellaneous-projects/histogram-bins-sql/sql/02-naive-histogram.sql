-- The histogram the quick way: group by the minutes divided by ten and
-- count. It goes wrong twice. SQLite divides whole numbers toward zero, so
-- -9 / 10 and 9 / 10 are both 0 and the bin at zero swallows everything from
-- -9 to 9, nineteen minutes wide against ten. The bin printed below it holds
-- -19 to -10, so of the readings that belong under its heading only the ones
-- exactly on -10 are there. And GROUP BY can
-- only return bins that have a row, so every empty bin is missing from the
-- report: the reader sees the bins either side of a gap sitting next to each
-- other and nothing to say the gap is there. The headings below zero are
-- wrong as well, for the same reason: the bin printed as -30 to -21 holds
-- the readings from -39 to -30.
SELECT
    minutes / 10 AS bin,
    printf('%d to %d', (minutes / 10) * 10, (minutes / 10) * 10 + 9) AS span,
    COUNT(*) AS deliveries
FROM deliveries
GROUP BY minutes / 10
ORDER BY bin;
