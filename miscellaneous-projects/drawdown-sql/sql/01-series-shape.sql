-- The series at a glance, ending on the split that motivates the build:
-- this portfolio finishes 27.40 percent up, and still spent 25 of its 40
-- days below a peak it had already reached. Endpoints measure the trip;
-- drawdown measures what it felt like to be on it.
SELECT COUNT(*) AS days,
       MIN(value_date) AS first_day,
       MAX(value_date) AS last_day,
       (SELECT ROUND(value_cents / 100.0, 2) FROM portfolio ORDER BY value_date LIMIT 1) AS start_value,
       (SELECT ROUND(value_cents / 100.0, 2) FROM portfolio ORDER BY value_date DESC LIMIT 1) AS end_value,
       ROUND(100.0 * ((SELECT value_cents FROM portfolio ORDER BY value_date DESC LIMIT 1)
                      - (SELECT value_cents FROM portfolio ORDER BY value_date LIMIT 1))
             / (SELECT value_cents FROM portfolio ORDER BY value_date LIMIT 1), 2) AS overall_gain_pct,
       ROUND(MAX(value_cents) / 100.0, 2) AS highest_value,
       (SELECT MIN(value_date) FROM portfolio
        WHERE value_cents = (SELECT MAX(value_cents) FROM portfolio)) AS highest_first_set,
       (SELECT COUNT(*) FROM (SELECT value_cents,
                                     MAX(value_cents) OVER (ORDER BY value_date
                                                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS peak_cents
                              FROM portfolio) WHERE value_cents = peak_cents) AS days_at_peak,
       (SELECT COUNT(*) FROM (SELECT value_cents,
                                     MAX(value_cents) OVER (ORDER BY value_date
                                                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS peak_cents
                              FROM portfolio) WHERE value_cents < peak_cents) AS days_underwater
FROM portfolio;
