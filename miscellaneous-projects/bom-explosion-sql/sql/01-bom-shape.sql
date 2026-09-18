-- The bill of materials at a glance. A product is built from parts and is
-- part of nothing else, a subassembly is built from parts and goes into
-- something, and a raw part is bought in and built from nothing. Then the
-- lines of the bill, and the order lines and units on this week's build plan.
SELECT (SELECT COUNT(DISTINCT parent) FROM bom
        WHERE parent NOT IN (SELECT child FROM bom)) AS products,
       (SELECT COUNT(DISTINCT parent) FROM bom
        WHERE parent IN (SELECT child FROM bom)) AS subassemblies,
       (SELECT COUNT(DISTINCT child) FROM bom
        WHERE child NOT IN (SELECT parent FROM bom)) AS raw_parts,
       (SELECT COUNT(*) FROM bom) AS bom_lines,
       (SELECT COUNT(*) FROM orders) AS order_lines,
       (SELECT SUM(qty) FROM orders) AS units_ordered;
