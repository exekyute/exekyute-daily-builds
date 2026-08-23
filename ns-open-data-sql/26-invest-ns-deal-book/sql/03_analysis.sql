-- 03_analysis.sql
-- Every breakdown, then all of them stacked into one sectioned result table
-- (deal_book). Dollar math stays in DECIMAL(18,2) end to end; percentages are
-- display values rounded to two decimals after the exact division. Every
-- ranking ends in a unique tie-breaker, so row order never depends on the
-- engine's scan order.

-- The number every breakdown has to tie back to. Blank contributions are not
-- in the sum, because sum() skips NULL, and they are counted on their own row
-- in the summary section rather than folded into zero.
CREATE OR REPLACE TABLE grand_total AS
SELECT
    count(*)                                    AS deals,
    count(*) FILTER (WHERE has_contribution)    AS funded_deals,
    CAST(COALESCE(sum(contribution), 0) AS DECIMAL(18,2)) AS amount
FROM clean_deals;

-- Contribution classes. Every deal lands in exactly one, and the four counts
-- add back to the row count, so nothing is dropped without being reported.
CREATE OR REPLACE TABLE contribution_classes AS
SELECT
    count(*) FILTER (WHERE NOT has_contribution)                     AS blank_deals,
    CAST(COALESCE(sum(contribution) FILTER (WHERE contribution = 0), 0)
         AS DECIMAL(18,2))                                           AS zero_amount,
    count(*) FILTER (WHERE has_contribution AND contribution = 0)    AS zero_deals,
    count(*) FILTER (WHERE has_contribution AND contribution < 0)    AS negative_deals,
    CAST(COALESCE(sum(contribution) FILTER (WHERE contribution < 0), 0)
         AS DECIMAL(18,2))                                           AS negative_amount,
    count(*) FILTER (WHERE has_contribution AND contribution > 0)    AS positive_deals
FROM clean_deals;

-- Geography classes: deals whose county label is not a county, deals with no
-- usable coordinate pair, and deals whose coordinates land outside Nova
-- Scotia. All of them stay in the money totals.
CREATE OR REPLACE TABLE geography_classes AS
SELECT
    count(*) FILTER (WHERE NOT county_is_geographic)   AS non_county_deals,
    CAST(COALESCE(sum(contribution) FILTER (WHERE NOT county_is_geographic), 0)
         AS DECIMAL(18,2))                             AS non_county_amount,
    count(*) FILTER (WHERE NOT is_mappable)            AS not_mappable_deals,
    CAST(COALESCE(sum(contribution) FILTER (WHERE NOT is_mappable), 0)
         AS DECIMAL(18,2))                             AS not_mappable_amount,
    count(*) FILTER (WHERE is_mappable AND NOT in_ns_bounds) AS out_of_bounds_deals,
    CAST(COALESCE(sum(contribution) FILTER (WHERE is_mappable AND NOT in_ns_bounds), 0)
         AS DECIMAL(18,2))                             AS out_of_bounds_amount,
    count(*) FILTER (WHERE in_ns_bounds)               AS in_bounds_deals
FROM clean_deals;

-- Contribution by sector, ranked by dollars, tie broken on the sector name.
CREATE OR REPLACE TABLE sector_totals AS
SELECT
    row_number() OVER (ORDER BY sum(c.contribution) DESC NULLS LAST, s.nsbi_sector) AS rnk,
    s.nsbi_sector,
    count(*) AS deals,
    CAST(COALESCE(sum(c.contribution), 0) AS DECIMAL(18,2)) AS amount
FROM clean_deals c
JOIN sector_display s USING (sector_key)
GROUP BY s.nsbi_sector
ORDER BY rnk;

-- Contribution by county, ranked by dollars, tie broken on the county name.
CREATE OR REPLACE TABLE county_totals AS
SELECT
    row_number() OVER (ORDER BY sum(c.contribution) DESC NULLS LAST, y.nsbi_county) AS rnk,
    y.nsbi_county,
    y.county_is_geographic,
    count(*) AS deals,
    CAST(COALESCE(sum(c.contribution), 0) AS DECIMAL(18,2)) AS amount
FROM clean_deals c
JOIN county_display y USING (county_key)
GROUP BY y.nsbi_county, y.county_is_geographic
ORDER BY rnk;

-- Contribution by deal type, ranked by dollars, tie broken on the label.
CREATE OR REPLACE TABLE deal_type_totals AS
SELECT
    row_number() OVER (ORDER BY sum(c.contribution) DESC NULLS LAST, t.deal_type) AS rnk,
    t.deal_type,
    count(*) AS deals,
    CAST(COALESCE(sum(c.contribution), 0) AS DECIMAL(18,2)) AS amount
FROM clean_deals c
JOIN deal_type_display t USING (deal_type_key)
GROUP BY t.deal_type
ORDER BY rnk;

-- Contribution by fiscal year, in year order, with the change against the
-- previous observed year from LAG. The first year has no prior, so its change
-- columns stay blank rather than reading as zero.
CREATE OR REPLACE TABLE fiscal_year_totals AS
SELECT
    row_number() OVER (ORDER BY fy_start) AS rnk,
    fiscal_year,
    fy_start,
    count(*) AS deals,
    CAST(COALESCE(sum(contribution), 0) AS DECIMAL(18,2)) AS amount,
    CAST(
        sum(contribution) - lag(sum(contribution)) OVER (ORDER BY fy_start)
        AS DECIMAL(18,2)
    ) AS yoy_change,
    CAST(ROUND(
        (sum(contribution) - lag(sum(contribution)) OVER (ORDER BY fy_start))
        / lag(sum(contribution)) OVER (ORDER BY fy_start) * 100, 2)
        AS DECIMAL(9,2)
    ) AS yoy_pct
FROM clean_deals
GROUP BY fiscal_year, fy_start
ORDER BY fy_start;

-- Top recipients over the whole window, ranked by dollars, tie broken on the
-- account name, which is unique per account key.
CREATE OR REPLACE TABLE recipient_totals AS
SELECT
    row_number() OVER (ORDER BY sum(c.contribution) DESC NULLS LAST, a.account_name) AS rnk,
    a.account_name,
    count(*) AS deals,
    CAST(COALESCE(sum(c.contribution), 0) AS DECIMAL(18,2)) AS amount
FROM clean_deals c
JOIN account_display a USING (account_key)
GROUP BY a.account_name
ORDER BY rnk;

-- Deal-type mix inside each fiscal year: dollars per deal type per year, with
-- each type's share of that year's contribution. Ordered by year, then
-- dollars, then the label.
CREATE OR REPLACE TABLE deal_type_mix AS
SELECT
    row_number() OVER (ORDER BY c.fy_start, sum(c.contribution) DESC NULLS LAST, t.deal_type) AS rnk,
    c.fiscal_year,
    c.fy_start,
    t.deal_type,
    count(*) AS deals,
    CAST(COALESCE(sum(c.contribution), 0) AS DECIMAL(18,2)) AS amount,
    CAST(ROUND(
        COALESCE(sum(c.contribution), 0)
        / (SELECT amount FROM fiscal_year_totals f WHERE f.fy_start = c.fy_start) * 100, 2)
        AS DECIMAL(9,2)
    ) AS year_share_pct
FROM clean_deals c
JOIN deal_type_display t USING (deal_type_key)
GROUP BY c.fiscal_year, c.fy_start, t.deal_type
ORDER BY rnk;

-- The sectioned deal book. Sections, in file order:
--   summary        headline figures and every counted exclusion class
--   totals_tie     five independent re-summations, all equal to the grand total
--   by_sector      every sector with its share of total contribution
--   by_county      every county label with its share of total contribution
--   by_deal_type   every deal type with its share of total contribution
--   by_fiscal_year dollars per year with the year-over-year change
--   top_recipients the top accounts by total contribution
--   deal_type_mix  deal type by fiscal year, with each type's share of its year
CREATE OR REPLACE TABLE deal_book AS
WITH sections AS (

    SELECT
        1 AS section_order, 'summary' AS section, 1 AS rank,
        'total_deals_and_contribution' AS measure,
        '' AS fiscal_year, '' AS nsbi_sector, '' AS nsbi_county,
        '' AS deal_type, '' AS account_name,
        deals,
        amount,
        CAST(100.00 AS DECIMAL(9,2)) AS share_pct,
        CAST(NULL AS DECIMAL(18,2)) AS yoy_change,
        CAST(NULL AS DECIMAL(9,2)) AS yoy_pct
    FROM grand_total

    UNION ALL

    SELECT
        1, 'summary', 2, 'deals_with_a_contribution_value', '', '', '', '', '',
        (SELECT funded_deals FROM grand_total),
        (SELECT amount FROM grand_total),
        CAST(100.00 AS DECIMAL(9,2)),
        NULL, NULL

    UNION ALL

    SELECT
        1, 'summary', 3, 'blank_contribution_deals', '', '', '', '', '',
        (SELECT blank_deals FROM contribution_classes),
        NULL, NULL, NULL, NULL

    UNION ALL

    SELECT
        1, 'summary', 4, 'zero_contribution_deals', '', '', '', '', '',
        (SELECT zero_deals FROM contribution_classes),
        (SELECT zero_amount FROM contribution_classes),
        CAST(0.00 AS DECIMAL(9,2)),
        NULL, NULL

    UNION ALL

    SELECT
        1, 'summary', 5, 'negative_contribution_deals', '', '', '', '', '',
        (SELECT negative_deals FROM contribution_classes),
        (SELECT negative_amount FROM contribution_classes),
        CAST(0.00 AS DECIMAL(9,2)),
        NULL, NULL

    UNION ALL

    SELECT
        1, 'summary', 6, 'non_county_label_deals', '', '', '', '', '',
        (SELECT non_county_deals FROM geography_classes),
        (SELECT non_county_amount FROM geography_classes),
        (SELECT CAST(ROUND(non_county_amount / (SELECT amount FROM grand_total) * 100, 2)
                AS DECIMAL(9,2)) FROM geography_classes),
        NULL, NULL

    UNION ALL

    SELECT
        1, 'summary', 7, 'deals_without_coordinates', '', '', '', '', '',
        (SELECT not_mappable_deals FROM geography_classes),
        (SELECT not_mappable_amount FROM geography_classes),
        (SELECT CAST(ROUND(not_mappable_amount / (SELECT amount FROM grand_total) * 100, 2)
                AS DECIMAL(9,2)) FROM geography_classes),
        NULL, NULL

    UNION ALL

    SELECT
        1, 'summary', 8, 'deals_outside_nova_scotia', '', '', '', '', '',
        (SELECT out_of_bounds_deals FROM geography_classes),
        (SELECT out_of_bounds_amount FROM geography_classes),
        (SELECT CAST(ROUND(out_of_bounds_amount / (SELECT amount FROM grand_total) * 100, 2)
                AS DECIMAL(9,2)) FROM geography_classes),
        NULL, NULL

    UNION ALL

    SELECT
        1, 'summary', 9, 'top_sector', '', nsbi_sector, '', '', '',
        deals, amount,
        CAST(ROUND(amount / (SELECT amount FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        NULL, NULL
    FROM sector_totals WHERE rnk = 1

    UNION ALL

    SELECT
        1, 'summary', 10, 'top_county', '', '', nsbi_county, '', '',
        deals, amount,
        CAST(ROUND(amount / (SELECT amount FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        NULL, NULL
    FROM county_totals WHERE rnk = 1

    UNION ALL

    SELECT
        1, 'summary', 11, 'top_deal_type', '', '', '', deal_type, '',
        deals, amount,
        CAST(ROUND(amount / (SELECT amount FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        NULL, NULL
    FROM deal_type_totals WHERE rnk = 1

    UNION ALL

    SELECT
        1, 'summary', 12, 'top_recipient', '', '', '', '', account_name,
        deals, amount,
        CAST(ROUND(amount / (SELECT amount FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        NULL, NULL
    FROM recipient_totals WHERE rnk = 1

    UNION ALL

    SELECT
        2, 'totals_tie', 1, 'sum_by_sector', '', '', '', '', '',
        (SELECT sum(deals) FROM sector_totals),
        (SELECT CAST(sum(amount) AS DECIMAL(18,2)) FROM sector_totals),
        NULL, NULL, NULL

    UNION ALL

    SELECT
        2, 'totals_tie', 2, 'sum_by_county', '', '', '', '', '',
        (SELECT sum(deals) FROM county_totals),
        (SELECT CAST(sum(amount) AS DECIMAL(18,2)) FROM county_totals),
        NULL, NULL, NULL

    UNION ALL

    SELECT
        2, 'totals_tie', 3, 'sum_by_deal_type', '', '', '', '', '',
        (SELECT sum(deals) FROM deal_type_totals),
        (SELECT CAST(sum(amount) AS DECIMAL(18,2)) FROM deal_type_totals),
        NULL, NULL, NULL

    UNION ALL

    SELECT
        2, 'totals_tie', 4, 'sum_by_fiscal_year', '', '', '', '', '',
        (SELECT sum(deals) FROM fiscal_year_totals),
        (SELECT CAST(sum(amount) AS DECIMAL(18,2)) FROM fiscal_year_totals),
        NULL, NULL, NULL

    UNION ALL

    SELECT
        2, 'totals_tie', 5, 'sum_by_recipient', '', '', '', '', '',
        (SELECT sum(deals) FROM recipient_totals),
        (SELECT CAST(sum(amount) AS DECIMAL(18,2)) FROM recipient_totals),
        NULL, NULL, NULL

    UNION ALL

    SELECT
        3, 'by_sector', rnk, '', '', nsbi_sector, '', '', '',
        deals, amount,
        CAST(ROUND(amount / (SELECT amount FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        NULL, NULL
    FROM sector_totals

    UNION ALL

    SELECT
        4, 'by_county', rnk, CASE WHEN county_is_geographic THEN '' ELSE 'not_a_county' END,
        '', '', nsbi_county, '', '',
        deals, amount,
        CAST(ROUND(amount / (SELECT amount FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        NULL, NULL
    FROM county_totals

    UNION ALL

    SELECT
        5, 'by_deal_type', rnk, '', '', '', '', deal_type, '',
        deals, amount,
        CAST(ROUND(amount / (SELECT amount FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        NULL, NULL
    FROM deal_type_totals

    UNION ALL

    SELECT
        6, 'by_fiscal_year', rnk, '', fiscal_year, '', '', '', '',
        deals, amount,
        CAST(ROUND(amount / (SELECT amount FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        yoy_change, yoy_pct
    FROM fiscal_year_totals

    UNION ALL

    SELECT
        7, 'top_recipients', rnk, '', '', '', '', '', account_name,
        deals, amount,
        CAST(ROUND(amount / (SELECT amount FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        NULL, NULL
    FROM recipient_totals
    WHERE rnk <= (SELECT n FROM top_recipients_n)

    UNION ALL

    SELECT
        8, 'deal_type_mix', rnk, '', fiscal_year, '', '', deal_type, '',
        deals, amount,
        year_share_pct,
        NULL, NULL
    FROM deal_type_mix
)
SELECT * FROM sections
ORDER BY section_order, rank;

-- BI mart: one cleaned row per source deal, carrying the coordinates Tableau
-- maps and the flags the guide filters on. Its contribution column sums to the
-- grand total.
CREATE OR REPLACE TABLE mart_deal_book AS
SELECT
    c.object_id,
    c.fiscal_year,
    c.fy_start AS fiscal_year_start,
    s.nsbi_sector,
    y.nsbi_county,
    CASE WHEN c.county_is_geographic THEN 1 ELSE 0 END AS county_is_geographic,
    t.deal_type,
    a.account_name,
    c.place_name,
    c.postalcode,
    c.contribution AS nsbi_financial_contribution,
    CASE WHEN c.has_contribution THEN 1 ELSE 0 END AS has_contribution,
    c.latitude,
    c.longitude,
    CASE WHEN c.is_mappable THEN 1 ELSE 0 END AS is_mappable,
    CASE WHEN c.in_ns_bounds THEN 1 ELSE 0 END AS in_ns_bounds
FROM clean_deals c
JOIN sector_display s    USING (sector_key)
JOIN county_display y    USING (county_key)
JOIN deal_type_display t USING (deal_type_key)
JOIN account_display a   USING (account_key)
ORDER BY c.object_id;

-- Dashboard cube: the same money, aggregated to the grain the browser page
-- needs (fiscal year, sector, county, deal type). Every figure the dashboard
-- shows is re-derived from these rows, and their contribution sums to the
-- grand total, so the page and the golden file cannot drift apart.
CREATE OR REPLACE TABLE dash_deal_book AS
SELECT
    c.fiscal_year,
    c.fy_start AS fiscal_year_start,
    s.nsbi_sector,
    y.nsbi_county,
    CASE WHEN c.county_is_geographic THEN 1 ELSE 0 END AS county_is_geographic,
    t.deal_type,
    count(*) AS deals,
    count(*) FILTER (WHERE c.has_contribution) AS funded_deals,
    count(*) FILTER (WHERE NOT c.has_contribution) AS blank_deals,
    count(*) FILTER (WHERE c.has_contribution AND c.contribution = 0) AS zero_deals,
    count(*) FILTER (WHERE c.is_mappable) AS mappable_deals,
    count(*) FILTER (WHERE c.in_ns_bounds) AS in_bounds_deals,
    CAST(COALESCE(sum(c.contribution), 0) AS DECIMAL(18,2)) AS contribution
FROM clean_deals c
JOIN sector_display s    USING (sector_key)
JOIN county_display y    USING (county_key)
JOIN deal_type_display t USING (deal_type_key)
GROUP BY c.fiscal_year, c.fy_start, s.nsbi_sector, y.nsbi_county,
         c.county_is_geographic, t.deal_type
ORDER BY c.fy_start, s.nsbi_sector, y.nsbi_county, t.deal_type;
