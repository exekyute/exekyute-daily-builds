-- 03_analysis.sql
-- Every breakdown, then the sectioned result table (fish_landings).
--
-- The suppression rule, applied per measure and never as a whole-row drop:
--   * a row with blank kilograms is excluded from kilogram sums and from
--     price per kg, but still counted in dollar sums when dollars are present
--   * a row with blank dollars is excluded from dollar sums and from price per
--     kg, but still counted in kilogram sums when kilograms are present
--   * neither blank is ever read as zero
-- SQL's sum() already skips NULL, so a blank measure leaves that measure's sum
-- untouched while the row's other measure still lands. Price per kg is the one
-- figure that needs both measures on the same row, so it is built from the
-- 'both_present' subset only, which is why priced_dollars and priced_kgs are
-- carried separately from the headline sums.
--
-- Dollar and kilogram math stays in DECIMAL(18,2) end to end. Percentages and
-- price per kg are display values rounded after the exact decimal division.

-- Grand totals over the port rows. Every breakdown must tie back to these,
-- dollars and kilograms independently.
CREATE OR REPLACE TABLE grand_total AS
SELECT
    records, kgs, dollars, priced_kgs, priced_dollars,
    CASE
        WHEN priced_kgs > (SELECT min_kgs_for_price FROM constants)
        THEN CAST(ROUND(priced_dollars / priced_kgs, 4) AS DECIMAL(18,4))
    END AS price_per_kg
FROM (
    SELECT
        count(*)                                  AS records,
        CAST(sum(kgs) AS DECIMAL(18,2))           AS kgs,
        CAST(sum(dollars) AS DECIMAL(18,2))       AS dollars,
        CAST(sum(CASE WHEN measure_class = 'both_present' THEN kgs END)
             AS DECIMAL(18,2))                    AS priced_kgs,
        CAST(sum(CASE WHEN measure_class = 'both_present' THEN dollars END)
             AS DECIMAL(18,2))                    AS priced_dollars
    FROM clean_landings
);

-- Dollars and kilograms by port. Port identity is (county, port), so the six
-- repeated port names across the province stay separate places.
CREATE OR REPLACE TABLE port_totals AS
SELECT
    row_number() OVER (ORDER BY dollars DESC NULLS LAST, county, port) AS rnk,
    county, port, port_label, is_named_port,
    records, kgs, dollars,
    CASE
        WHEN priced_kgs > (SELECT min_kgs_for_price FROM constants)
        THEN CAST(ROUND(priced_dollars / priced_kgs, 4) AS DECIMAL(18,4))
    END AS price_per_kg
FROM (
    SELECT
        county, port, port_label, is_named_port,
        count(*)                                  AS records,
        CAST(sum(kgs) AS DECIMAL(18,2))           AS kgs,
        CAST(sum(dollars) AS DECIMAL(18,2))       AS dollars,
        CAST(sum(CASE WHEN measure_class = 'both_present' THEN kgs END)
             AS DECIMAL(18,2))                    AS priced_kgs,
        CAST(sum(CASE WHEN measure_class = 'both_present' THEN dollars END)
             AS DECIMAL(18,2))                    AS priced_dollars
    FROM clean_landings
    GROUP BY county, port, port_label, is_named_port
)
ORDER BY rnk;

-- Dollars and kilograms by county.
CREATE OR REPLACE TABLE county_totals AS
SELECT
    row_number() OVER (ORDER BY dollars DESC NULLS LAST, county) AS rnk,
    county, records, kgs, dollars,
    CASE
        WHEN priced_kgs > (SELECT min_kgs_for_price FROM constants)
        THEN CAST(ROUND(priced_dollars / priced_kgs, 4) AS DECIMAL(18,4))
    END AS price_per_kg
FROM (
    SELECT
        county,
        count(*)                                  AS records,
        CAST(sum(kgs) AS DECIMAL(18,2))           AS kgs,
        CAST(sum(dollars) AS DECIMAL(18,2))       AS dollars,
        CAST(sum(CASE WHEN measure_class = 'both_present' THEN kgs END)
             AS DECIMAL(18,2))                    AS priced_kgs,
        CAST(sum(CASE WHEN measure_class = 'both_present' THEN dollars END)
             AS DECIMAL(18,2))                    AS priced_dollars
    FROM clean_landings
    GROUP BY county
)
ORDER BY rnk;

-- Dollars and kilograms by year, with the year-over-year move in landed value
-- taken by LAG over the observed year sequence.
CREATE OR REPLACE TABLE year_totals AS
SELECT
    year, records, kgs, dollars,
    CASE
        WHEN priced_kgs > (SELECT min_kgs_for_price FROM constants)
        THEN CAST(ROUND(priced_dollars / priced_kgs, 4) AS DECIMAL(18,4))
    END AS price_per_kg,
    CAST(dollars - lag(dollars) OVER (ORDER BY year) AS DECIMAL(18,2)) AS yoy_change,
    CAST(ROUND(
        (dollars - lag(dollars) OVER (ORDER BY year))
        / lag(dollars) OVER (ORDER BY year) * 100, 2)
        AS DECIMAL(9,2)) AS yoy_pct
FROM (
    SELECT
        year,
        count(*)                                  AS records,
        CAST(sum(kgs) AS DECIMAL(18,2))           AS kgs,
        CAST(sum(dollars) AS DECIMAL(18,2))       AS dollars,
        CAST(sum(CASE WHEN measure_class = 'both_present' THEN kgs END)
             AS DECIMAL(18,2))                    AS priced_kgs,
        CAST(sum(CASE WHEN measure_class = 'both_present' THEN dollars END)
             AS DECIMAL(18,2))                    AS priced_dollars
    FROM clean_landings
    GROUP BY year
)
ORDER BY year;

-- Coverage: the province's own 'Total for <County> County' figure against the
-- sum of that county's port rows for the same year. The gap is what port-level
-- suppression hides. One output row per excluded aggregate row, so all 144 of
-- them stay visible instead of being dropped on the floor.
CREATE OR REPLACE TABLE county_coverage AS
SELECT
    COALESCE(b.year, p.year)     AS year,
    COALESCE(b.county, p.county) AS county,
    b.records,
    b.dollars                    AS bottom_up_dollars,
    p.published_dollars,
    CAST(b.dollars - p.published_dollars AS DECIMAL(18,2)) AS gap_dollars,
    CASE
        WHEN p.published_dollars IS NOT NULL AND p.published_dollars <> 0
        THEN CAST(ROUND((b.dollars - p.published_dollars)
                        / p.published_dollars * 100, 2) AS DECIMAL(9,2))
    END AS gap_pct
FROM (
    SELECT year, county, count(*) AS records,
           CAST(sum(dollars) AS DECIMAL(18,2)) AS dollars
    FROM clean_landings
    GROUP BY year, county
) b
FULL OUTER JOIN published_county_totals p USING (year, county)
ORDER BY county, year;

-- The sectioned result. Sections in file order:
--   summary          headline figures
--   row_classes      every source row accounted for, by grain and by measure
--   totals_tie       the port, county, and year breakdowns re-summed
--   top_ports        the Pareto, with share and running cumulative share
--   by_county        all 18 counties
--   by_year          the year trend of landed value
--   county_coverage  bottom-up port dollars against the published county figure
CREATE OR REPLACE TABLE fish_landings AS
WITH sections AS (

    SELECT
        1 AS section_order, 'summary' AS section, 1 AS rank,
        'grand_total' AS measure,
        '' AS year, '' AS county, '' AS port,
        records,
        kgs,
        dollars,
        CAST(NULL AS DECIMAL(18,2)) AS published_dollars,
        price_per_kg,
        CAST(100.00 AS DECIMAL(9,2)) AS share_pct,
        CAST(NULL AS DECIMAL(9,2))   AS cumulative_share_pct,
        CAST(NULL AS DECIMAL(18,2))  AS delta,
        CAST(NULL AS DECIMAL(9,2))   AS delta_pct
    FROM grand_total

    UNION ALL

    SELECT
        1, 'summary', 2, 'top_port',
        '', county, port_label,
        records, kgs, dollars, NULL, price_per_kg,
        CAST(ROUND(dollars / (SELECT dollars FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        NULL, NULL, NULL
    FROM port_totals WHERE rnk = 1

    UNION ALL

    SELECT
        1, 'summary', 3, 'top_10_ports', '', '', '',
        (SELECT sum(records) FROM port_totals WHERE rnk <= 10),
        (SELECT CAST(sum(kgs) AS DECIMAL(18,2)) FROM port_totals WHERE rnk <= 10),
        (SELECT CAST(sum(dollars) AS DECIMAL(18,2)) FROM port_totals WHERE rnk <= 10),
        NULL, NULL,
        (SELECT CAST(ROUND(sum(dollars) / (SELECT dollars FROM grand_total) * 100, 2) AS DECIMAL(9,2))
         FROM port_totals WHERE rnk <= 10),
        NULL, NULL, NULL

    UNION ALL

    SELECT
        1, 'summary', 4, 'named_ports', '', '', '',
        (SELECT sum(records) FROM port_totals WHERE is_named_port = 1),
        (SELECT CAST(sum(kgs) AS DECIMAL(18,2)) FROM port_totals WHERE is_named_port = 1),
        (SELECT CAST(sum(dollars) AS DECIMAL(18,2)) FROM port_totals WHERE is_named_port = 1),
        NULL, NULL,
        (SELECT CAST(ROUND(sum(dollars) / (SELECT dollars FROM grand_total) * 100, 2) AS DECIMAL(9,2))
         FROM port_totals WHERE is_named_port = 1),
        NULL, NULL, NULL

    UNION ALL

    SELECT
        1, 'summary', 5, 'residual_other_buckets', '', '', '',
        (SELECT sum(records) FROM port_totals WHERE is_named_port = 0),
        (SELECT CAST(sum(kgs) AS DECIMAL(18,2)) FROM port_totals WHERE is_named_port = 0),
        (SELECT CAST(sum(dollars) AS DECIMAL(18,2)) FROM port_totals WHERE is_named_port = 0),
        NULL, NULL,
        (SELECT CAST(ROUND(sum(dollars) / (SELECT dollars FROM grand_total) * 100, 2) AS DECIMAL(9,2))
         FROM port_totals WHERE is_named_port = 0),
        NULL, NULL, NULL

    UNION ALL

    -- How much of the province's own published figure the port rows reach.
    -- delta is the port-level sum minus the published sum, so a negative delta
    -- is landed value the province reports at county level but suppresses at
    -- port level.
    SELECT
        1, 'summary', 6, 'published_county_dollars', '', '', '',
        (SELECT count(*) FROM published_county_totals),
        NULL, NULL,
        (SELECT CAST(sum(published_dollars) AS DECIMAL(18,2)) FROM published_county_totals),
        NULL, NULL, NULL,
        (SELECT CAST((SELECT dollars FROM grand_total) - sum(published_dollars) AS DECIMAL(18,2))
         FROM published_county_totals),
        (SELECT CAST(ROUND(((SELECT dollars FROM grand_total) - sum(published_dollars))
                           / sum(published_dollars) * 100, 2) AS DECIMAL(9,2))
         FROM published_county_totals)

    UNION ALL

    -- Every source row lands in exactly one grain class and exactly one
    -- measure class. The counts add back to the 2,300 rows in the snapshot.
    SELECT
        2, 'row_classes', 1, 'snapshot_rows_total', '', '', '',
        (SELECT count(*) FROM classified),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT
        2, 'row_classes', 2, 'excluded_county_total_rows', '', '', '',
        (SELECT count(*) FROM classified WHERE row_grain = 'county_total'),
        NULL, NULL,
        (SELECT CAST(sum(published_dollars) AS DECIMAL(18,2)) FROM published_county_totals),
        NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT
        2, 'row_classes', 3, 'port_rows_analysed', '', '', '',
        (SELECT count(*) FROM clean_landings),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT
        2, 'row_classes', 4, 'port_rows_both_present', '', '', '',
        (SELECT count(*) FROM clean_landings WHERE measure_class = 'both_present'),
        (SELECT CAST(sum(kgs) AS DECIMAL(18,2)) FROM clean_landings WHERE measure_class = 'both_present'),
        (SELECT CAST(sum(dollars) AS DECIMAL(18,2)) FROM clean_landings WHERE measure_class = 'both_present'),
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    -- Kilograms reported, dollars suppressed: counted in kilogram sums,
    -- excluded from dollar sums and from price per kg.
    SELECT
        2, 'row_classes', 5, 'port_rows_kgs_only', '', '', '',
        (SELECT count(*) FROM clean_landings WHERE measure_class = 'kgs_only'),
        (SELECT CAST(sum(kgs) AS DECIMAL(18,2)) FROM clean_landings WHERE measure_class = 'kgs_only'),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    -- Dollars reported, kilograms suppressed: counted in dollar sums,
    -- excluded from kilogram sums and from price per kg.
    SELECT
        2, 'row_classes', 6, 'port_rows_dollars_only', '', '', '',
        (SELECT count(*) FROM clean_landings WHERE measure_class = 'dollars_only'),
        NULL,
        (SELECT CAST(sum(dollars) AS DECIMAL(18,2)) FROM clean_landings WHERE measure_class = 'dollars_only'),
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT
        2, 'row_classes', 7, 'port_rows_both_blank', '', '', '',
        (SELECT count(*) FROM clean_landings WHERE measure_class = 'both_blank'),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    -- An overlay on the rows above rather than a class of its own: how many
    -- port rows arrived carrying a wharf qualifier that was rolled into its
    -- base port. Ranks 1 to 7 partition the snapshot; this one does not.
    SELECT
        2, 'row_classes', 8, 'port_rows_wharf_qualifier_merged', '', '', '',
        (SELECT count(*) FROM clean_landings WHERE wharf_qualifier_merged = 1),
        (SELECT CAST(sum(kgs) AS DECIMAL(18,2)) FROM clean_landings WHERE wharf_qualifier_merged = 1),
        (SELECT CAST(sum(dollars) AS DECIMAL(18,2)) FROM clean_landings WHERE wharf_qualifier_merged = 1),
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    -- Each breakdown re-summed. Dollars and kilograms tie independently,
    -- because the two measures are suppressed independently.
    SELECT
        3, 'totals_tie', 1, 'sum_by_port', '', '', '',
        (SELECT sum(records) FROM port_totals),
        (SELECT CAST(sum(kgs) AS DECIMAL(18,2)) FROM port_totals),
        (SELECT CAST(sum(dollars) AS DECIMAL(18,2)) FROM port_totals),
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT
        3, 'totals_tie', 2, 'sum_by_county', '', '', '',
        (SELECT sum(records) FROM county_totals),
        (SELECT CAST(sum(kgs) AS DECIMAL(18,2)) FROM county_totals),
        (SELECT CAST(sum(dollars) AS DECIMAL(18,2)) FROM county_totals),
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT
        3, 'totals_tie', 3, 'sum_by_year', '', '', '',
        (SELECT sum(records) FROM year_totals),
        (SELECT CAST(sum(kgs) AS DECIMAL(18,2)) FROM year_totals),
        (SELECT CAST(sum(dollars) AS DECIMAL(18,2)) FROM year_totals),
        NULL, NULL, NULL, NULL, NULL, NULL

    UNION ALL

    SELECT
        4, 'top_ports', rnk, '',
        '', county, port_label,
        records, kgs, dollars, NULL, price_per_kg,
        CAST(ROUND(dollars / (SELECT dollars FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        CAST(ROUND(sum(dollars) OVER (ORDER BY rnk)
                   / (SELECT dollars FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        NULL, NULL
    FROM port_totals
    WHERE rnk <= (SELECT top_ports_n FROM constants)

    UNION ALL

    SELECT
        5, 'by_county', rnk, '',
        '', county, '',
        records, kgs, dollars, NULL, price_per_kg,
        CAST(ROUND(dollars / (SELECT dollars FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        NULL, NULL, NULL
    FROM county_totals

    UNION ALL

    SELECT
        6, 'by_year',
        row_number() OVER (ORDER BY year),
        '',
        CAST(year AS VARCHAR), '', '',
        records, kgs, dollars, NULL, price_per_kg,
        CAST(ROUND(dollars / (SELECT dollars FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        NULL,
        yoy_change, yoy_pct
    FROM year_totals

    UNION ALL

    SELECT
        7, 'county_coverage',
        row_number() OVER (ORDER BY county, year),
        '',
        CAST(year AS VARCHAR), county, '',
        records, NULL,
        bottom_up_dollars, published_dollars, NULL, NULL, NULL,
        gap_dollars, gap_pct
    FROM county_coverage
)
SELECT * FROM sections
ORDER BY section_order, rank;

-- BI mart: one row per analysed port record, so Tableau and Power BI can
-- re-derive every headline without repeating a single cleaning rule. The
-- excluded county aggregate rows are deliberately not in here; putting them in
-- would let a report double count the province.
--
-- The sort runs over every exported column, so any rows it still leaves tied
-- are byte-identical (repeated suppressed buyer rows at one port) and the file
-- is stable whichever order they land in.
CREATE OR REPLACE TABLE mart_fish_landings AS
SELECT
    year,
    county,
    port,
    port_label,
    is_named_port,
    kgs,
    dollars,
    measure_class
FROM clean_landings
ORDER BY year, county, port, port_label, is_named_port,
         dollars NULLS LAST, kgs NULLS LAST, measure_class;
