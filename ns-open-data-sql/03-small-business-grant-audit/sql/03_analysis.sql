-- 03_analysis.sql
-- Question: for each business type and year, how many recipients are there, how
-- many received each grant, and what share of all recipients does the type hold?
-- The share column is the concentration measure: it shows how top-heavy the
-- grants are across business types. Counts are on recipient records.

DROP TABLE IF EXISTS grants_by_type_year;
CREATE TABLE grants_by_type_year AS
WITH total AS (
    SELECT count(*) AS all_recipients
    FROM recipients
)
SELECT
    r.year,
    r.type_of_business,
    count(*)                                       AS recipients,
    count(*) FILTER (WHERE r.got_sbig)             AS sbig_recipients,
    count(*) FILTER (WHERE r.got_sbrsg)            AS sbrsg_recipients,
    round(100.0 * count(*) / t.all_recipients, 2)  AS pct_of_recipients
FROM recipients r
CROSS JOIN total t
GROUP BY r.year, r.type_of_business, t.all_recipients
ORDER BY r.year, recipients DESC, r.type_of_business;
