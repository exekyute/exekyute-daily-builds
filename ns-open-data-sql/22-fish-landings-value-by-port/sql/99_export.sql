-- 99_export.sql
-- Write the sectioned result and the BI mart. Both carry an explicit ORDER BY
-- ending in a unique tie-breaker, so the files are byte-stable run to run
-- whatever the engine version or thread count.

COPY (
    SELECT
        section, rank, measure, year, county, port,
        records, kgs, dollars, published_dollars, price_per_kg,
        share_pct, cumulative_share_pct, delta, delta_pct
    FROM fish_landings
    ORDER BY section_order, rank
) TO 'out/fish_landings.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        year, county, port, port_label, is_named_port,
        kgs, dollars, measure_class
    FROM mart_fish_landings
    ORDER BY year, county, port, port_label, is_named_port,
             dollars NULLS LAST, kgs NULLS LAST, measure_class
) TO 'out/mart_fish_landings.csv' (HEADER, DELIMITER ',');
