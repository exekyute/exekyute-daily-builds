-- How often each product appears, as a count of orders and a share of all
-- orders. These denominators are what lift corrects with later: espresso is
-- in 60 percent of orders, so it will co-occur with everything whether
-- customers care or not.
SELECT product,
       COUNT(DISTINCT order_id) AS orders_with_it,
       printf('%.1f%%', 100.0 * COUNT(DISTINCT order_id)
                        / (SELECT COUNT(DISTINCT order_id) FROM order_lines)) AS share_of_orders
FROM order_lines
GROUP BY product
ORDER BY orders_with_it DESC, product;
