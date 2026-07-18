-- 03_analysis.sql
-- Question this step answers: which regions carry the most registered short-term
-- rentals, and how commercial is each region's mix?
--
-- Classification rule (defined from the source's own categories, spec.md section
-- "The type-classification rule"): a short-term rental is a registration in either
-- 'commercial short-term rental' or 'whole-home primary residence'. The commercial
-- share is the commercial category's part of that STR total. The third category,
-- 'traditional tourist accommodation', is not an STR; it rides along as context.
--
-- The mart is one row per region: the STR count, its share of the provincial STR
-- total, a rank by count, the commercial share and a rank by that share, and the
-- larger of the region's two STR categories.

INSERT INTO str_pressure
WITH per_region AS (
    -- fold the long rows back to one row per region with one column per measure
    SELECT
        region,
        sum(CASE WHEN category IN ('commercial short-term rental',
                                   'whole-home primary residence')
                 THEN registrations END) AS total_registrations,
        sum(CASE WHEN category = 'commercial short-term rental'
                 THEN registrations END) AS commercial_count,
        sum(CASE WHEN category = 'whole-home primary residence'
                 THEN registrations END) AS whole_home_count,
        sum(CASE WHEN category = 'traditional tourist accommodation'
                 THEN registrations END) AS traditional_count
    FROM clean_registrations
    GROUP BY region
),
province AS (
    -- one provincial STR total, the denominator for every region's share
    SELECT sum(total_registrations) AS provincial_total
    FROM per_region
)
SELECT
    r.region,
    r.total_registrations,
    -- region's share of all registered STRs in the province, one decimal place
    round(r.total_registrations * 100.0 / p.provincial_total, 1) AS pct_of_province,
    -- rank by raw count, most first; equal totals share a rank
    dense_rank() OVER (ORDER BY r.total_registrations DESC) AS rank_by_count,
    r.commercial_count,
    r.whole_home_count,
    r.traditional_count,
    -- commercial registrations as a share of the region's STR total, one decimal place
    round(r.commercial_count * 100.0 / r.total_registrations, 1) AS commercial_share_pct,
    -- rank on the rounded share, so any two regions that display the same share
    -- also share the same rank
    dense_rank() OVER (
        ORDER BY round(r.commercial_count * 100.0 / r.total_registrations, 1) DESC
    ) AS rank_by_commercial_share,
    -- the larger of the two STR categories; a tie goes to the alphabetically first
    -- name, 'commercial short-term rental' (in this snapshot, Digby is the one tie)
    CASE
        WHEN r.whole_home_count > r.commercial_count THEN 'whole-home primary residence'
        ELSE 'commercial short-term rental'
    END AS dominant_type
FROM per_region r
CROSS JOIN province p;
