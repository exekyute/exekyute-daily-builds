-- 99_export.sql
-- Writes the deterministic corridor ranking to CSV, busiest segment first, with
-- section_id as the tie-break so the row order is fixed run to run.
-- Question answered: what is the final, ordered output?

COPY (
    SELECT
        aadt_rank,
        section_id,
        highway,
        section,
        county,
        section_description,
        section_length_km,
        current_year,
        current_aadt,
        prior_year,
        prior_aadt,
        yoy_growth_pct,
        growth_rank,
        capacity_threshold,
        over_capacity
    FROM corridor_ranking
    ORDER BY current_aadt DESC, section_id
) TO 'out/corridor_ranking.csv' (HEADER, DELIMITER ',');
