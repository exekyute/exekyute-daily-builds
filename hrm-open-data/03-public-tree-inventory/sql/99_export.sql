-- 99_export: write the golden result files and the one wide BI mart. Every
-- query ends in ORDER BY so each file is byte-for-byte reproducible.

COPY (
    SELECT species_rank, species_common, species_scientific, tree_count, share_of_all_pct
    FROM species_ranking
    ORDER BY species_rank, species_common
) TO 'out/species_ranking.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT dbh_class, tree_count, share_pct
    FROM dbh_class_distribution
    ORDER BY class_order
) TO 'out/dbh_class_distribution.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT wires, tree_count, share_pct
    FROM wires_distribution
    ORDER BY tree_count DESC, wires
) TO 'out/wires_distribution.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT setting, tree_count, share_pct
    FROM setting_distribution
    ORDER BY tree_count DESC, setting
) TO 'out/setting_distribution.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT metric, value
    FROM summary
    ORDER BY ord
) TO 'out/summary.csv' (HEADER, DELIMITER ',');

-- The BI mart: one row per tree, wide and denormalized for both dashboards.
COPY (
    SELECT
        tree_id,
        species_common,
        species_scientific,
        dbh,
        dbh_class,
        setting,
        wires,
        install_year,
        owner,
        status,
        lat,
        lon
    FROM trees_clean
    ORDER BY tree_id
) TO 'out/mart_trees.csv' (HEADER, DELIMITER ',');
