-- The trap, laid open. Asking which products are tagged red with
-- LIKE '%red%' searches for the three letters anywhere in the list, so it
-- also finds them inside other words. On this catalog it returns eight
-- products and four of them are not red: two are tagged reduced, one
-- infrared, and one tiered. The tag list is printed beside each row so the
-- wrong matches are visible without taking the count on trust.
SELECT product_id,
       name,
       tags
FROM products
WHERE tags LIKE '%red%'
ORDER BY product_id;
