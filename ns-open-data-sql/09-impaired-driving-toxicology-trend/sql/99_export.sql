-- 99_export.sql
-- Question this step answers: how is the final table written out, in a fixed order?
--
-- Year rows first (2015..2024), then the twelve month rows in calendar order.
-- The ORDER BY makes the output byte-for-byte reproducible so it can be diffed
-- against the committed golden file. run.py ensures the out/ folder exists.

COPY (
    SELECT dimension, period, period_num, total_deaths,
           positive, not_detected, tox_unavailable, pct_positive
    FROM toxicology_trend
    ORDER BY (dimension = 'month'), period_num
) TO 'out/toxicology_trend.csv' (HEADER, DELIMITER ',');
