-- 99_export.sql
-- Question this step answers: what is the final, deterministic table a reader should see?
-- Writes the mart twice from the same SELECT: out/str_pressure_index.csv is the
-- verification target that run.py diffs against expected/, and
-- bi/exports/mart_str_pressure.csv is the committed copy the Tableau guide connects
-- to, so the dashboard reads exactly the numbers the golden diff verified. The
-- ORDER BY makes both files byte-for-byte stable across runs: busiest regions
-- first, then region name to settle any remaining ties.

COPY (
    SELECT
        region,
        total_registrations,
        pct_of_province,
        rank_by_count,
        commercial_count,
        whole_home_count,
        traditional_count,
        commercial_share_pct,
        rank_by_commercial_share,
        dominant_type
    FROM str_pressure
    ORDER BY
        total_registrations DESC,
        region ASC
) TO 'out/str_pressure_index.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        region,
        total_registrations,
        pct_of_province,
        rank_by_count,
        commercial_count,
        whole_home_count,
        traditional_count,
        commercial_share_pct,
        rank_by_commercial_share,
        dominant_type
    FROM str_pressure
    ORDER BY
        total_registrations DESC,
        region ASC
) TO 'bi/exports/mart_str_pressure.csv' (HEADER, DELIMITER ',');
