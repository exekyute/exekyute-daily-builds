-- 03_analysis: roll the per-tree mart into the golden result tables. Every
-- table is built FROM trees_clean, so the species ranking, the two class
-- distributions, and the summary all add up to the same 78,896-tree total.

-- Species ranking: identified species only (the 'Unidentified' bucket is not a
-- species). Each species carries its representative scientific name, chosen as
-- the most frequent scientific name recorded under that common name, ties
-- broken alphabetically so the pick is deterministic. Share is of ALL trees,
-- so the ranking's counts plus the unidentified count equal the inventory.
CREATE OR REPLACE TABLE species_ranking AS
WITH ident AS (
    SELECT species_common, species_scientific
    FROM trees_clean
    WHERE species_common <> 'Unidentified'
),
counts AS (
    SELECT species_common, COUNT(*) AS tree_count
    FROM ident
    GROUP BY species_common
),
sci AS (
    SELECT
        species_common,
        species_scientific,
        ROW_NUMBER() OVER (
            PARTITION BY species_common
            ORDER BY COUNT(*) DESC, species_scientific
        ) AS rn
    FROM ident
    GROUP BY species_common, species_scientific
),
total AS (SELECT COUNT(*) AS all_trees FROM trees_clean)
SELECT
    RANK() OVER (ORDER BY c.tree_count DESC, c.species_common) AS species_rank,
    c.species_common,
    s.species_scientific,
    c.tree_count,
    CAST(ROUND(100.0 * c.tree_count / t.all_trees, 2) AS DECIMAL(6, 2))
        AS share_of_all_pct
FROM counts c
JOIN sci s
    ON s.species_common = c.species_common AND s.rn = 1
CROSS JOIN total t;

-- DBH size-class distribution across every tree, ordered by class code.
CREATE OR REPLACE TABLE dbh_class_distribution AS
SELECT
    dbh_class,
    CASE dbh_class
        WHEN 'Class 1-2' THEN 1
        WHEN 'Class 3-4' THEN 2
        WHEN 'Class 5-6' THEN 3
        WHEN 'Class 7-9' THEN 4
        ELSE 5
    END AS class_order,
    COUNT(*) AS tree_count,
    CAST(ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS DECIMAL(6, 2))
        AS share_pct
FROM trees_clean
GROUP BY dbh_class;

-- Wires-present distribution: the categorical dimension that stands in for the
-- condition rating the dataset does not carry.
CREATE OR REPLACE TABLE wires_distribution AS
SELECT
    wires,
    COUNT(*) AS tree_count,
    CAST(ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS DECIMAL(6, 2))
        AS share_pct
FROM trees_clean
GROUP BY wires;

-- General-location distribution (street right-of-way vs open space).
CREATE OR REPLACE TABLE setting_distribution AS
SELECT
    setting,
    COUNT(*) AS tree_count,
    CAST(ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS DECIMAL(6, 2))
        AS share_pct
FROM trees_clean
GROUP BY setting;

-- Summary: one row per headline metric, values as text so ints, decimals, and
-- names share a column. Every value is read from the tables above.
CREATE OR REPLACE TABLE summary AS
WITH t AS (
    SELECT
        COUNT(*) AS total_trees,
        COUNT(*) FILTER (WHERE species_common <> 'Unidentified') AS identified,
        COUNT(*) FILTER (WHERE species_common =  'Unidentified') AS unidentified,
        COUNT(DISTINCT species_common) FILTER (WHERE species_common <> 'Unidentified')
            AS distinct_species,
        COUNT(*) FILTER (WHERE install_year IS NOT NULL) AS with_year,
        MIN(install_year) AS year_min,
        MAX(install_year) AS year_max
    FROM trees_clean
),
top_sp AS (
    SELECT species_common, tree_count, share_of_all_pct
    FROM species_ranking
    WHERE species_rank = 1
    ORDER BY species_common
    LIMIT 1
),
top_dbh AS (
    SELECT dbh_class
    FROM dbh_class_distribution
    ORDER BY tree_count DESC, class_order
    LIMIT 1
)
SELECT ord, metric, value FROM (
    SELECT 1 AS ord, 'total_trees'          AS metric, CAST(t.total_trees      AS VARCHAR) AS value FROM t
    UNION ALL SELECT 2, 'identified_trees',   CAST(t.identified   AS VARCHAR) FROM t
    UNION ALL SELECT 3, 'unidentified_trees', CAST(t.unidentified AS VARCHAR) FROM t
    UNION ALL SELECT 4, 'distinct_species',   CAST(t.distinct_species AS VARCHAR) FROM t
    UNION ALL SELECT 5, 'top_species',        top_sp.species_common FROM top_sp
    UNION ALL SELECT 6, 'top_species_count',  CAST(top_sp.tree_count AS VARCHAR) FROM top_sp
    UNION ALL SELECT 7, 'top_species_share_pct', CAST(top_sp.share_of_all_pct AS VARCHAR) FROM top_sp
    UNION ALL SELECT 8, 'most_common_dbh_class', top_dbh.dbh_class FROM top_dbh
    UNION ALL SELECT 9, 'trees_with_install_year', CAST(t.with_year AS VARCHAR) FROM t
    UNION ALL SELECT 10, 'install_year_earliest', CAST(t.year_min AS VARCHAR) FROM t
    UNION ALL SELECT 11, 'install_year_latest',   CAST(t.year_max AS VARCHAR) FROM t
);

-- Headline: ready-to-print lines. run.py prints these; it computes nothing.
CREATE OR REPLACE TABLE headline AS
WITH m AS (
    SELECT
        MAX(CASE WHEN metric = 'total_trees'          THEN value END) AS total_trees,
        MAX(CASE WHEN metric = 'distinct_species'     THEN value END) AS distinct_species,
        MAX(CASE WHEN metric = 'top_species'          THEN value END) AS top_species,
        MAX(CASE WHEN metric = 'top_species_count'    THEN value END) AS top_species_count,
        MAX(CASE WHEN metric = 'top_species_share_pct' THEN value END) AS top_species_share,
        MAX(CASE WHEN metric = 'trees_with_install_year' THEN value END) AS with_year,
        MAX(CASE WHEN metric = 'install_year_earliest' THEN value END) AS year_min,
        MAX(CASE WHEN metric = 'install_year_latest'   THEN value END) AS year_max
    FROM summary
)
SELECT 1 AS ord,
       printf('HRM''s public-tree inventory holds %s trees across %s distinct species.',
              total_trees, distinct_species) AS line
FROM m
UNION ALL
SELECT 2,
       printf('Most common: %s with %s trees (%s%% of the inventory).',
              top_species, top_species_count, top_species_share)
FROM m
UNION ALL
SELECT 3,
       printf('%s trees carry a recorded planting year, spanning %s to %s.',
              with_year, year_min, year_max)
FROM m;
