-- The trap, laid open, with both mistakes a first pivot usually makes.
-- strftime('%w') numbers the days from Sunday as 0, so reading 0 as Monday
-- shifts every column one day: the column labelled mon holds Sunday and the
-- one labelled sun holds Saturday. This grid reports the cafe's busiest
-- day as Sunday, a day it is closed almost every week.
-- ELSE 0 is the second mistake. A week with no row for a weekday gets 0.00
-- in that column, so a closed day reads exactly like a day that opened and
-- sold nothing.
SELECT DATE(sale_date, 'weekday 0', '-6 days') AS week_of,
       printf('%.2f', SUM(CASE WHEN strftime('%w', sale_date) = '0' THEN cents ELSE 0 END) / 100.0) AS mon,
       printf('%.2f', SUM(CASE WHEN strftime('%w', sale_date) = '1' THEN cents ELSE 0 END) / 100.0) AS tue,
       printf('%.2f', SUM(CASE WHEN strftime('%w', sale_date) = '2' THEN cents ELSE 0 END) / 100.0) AS wed,
       printf('%.2f', SUM(CASE WHEN strftime('%w', sale_date) = '3' THEN cents ELSE 0 END) / 100.0) AS thu,
       printf('%.2f', SUM(CASE WHEN strftime('%w', sale_date) = '4' THEN cents ELSE 0 END) / 100.0) AS fri,
       printf('%.2f', SUM(CASE WHEN strftime('%w', sale_date) = '5' THEN cents ELSE 0 END) / 100.0) AS sat,
       printf('%.2f', SUM(CASE WHEN strftime('%w', sale_date) = '6' THEN cents ELSE 0 END) / 100.0) AS sun
FROM sales
GROUP BY week_of
ORDER BY week_of;
