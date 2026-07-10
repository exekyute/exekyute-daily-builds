-- 99_export.sql
-- Question this step answers: what is the final, deterministic table a reader should see?
-- Writes the mart to out/license_density.csv. The ORDER BY makes the file byte-for-byte
-- stable across runs: busiest communities first, then the largest type within each
-- community, then license type by name to settle any remaining ties.

COPY (
    SELECT
        community,
        community_total_licenses,
        community_rank,
        license_type,
        type_count,
        type_share_pct,
        is_dominant_type
    FROM license_density
    ORDER BY
        community_total_licenses DESC,
        community ASC,
        type_count DESC,
        license_type ASC
) TO 'out/license_density.csv' (HEADER, DELIMITER ',');
