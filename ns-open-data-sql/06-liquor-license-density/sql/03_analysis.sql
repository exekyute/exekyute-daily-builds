-- 03_analysis.sql
-- Question this step answers: how many permanent licenses does each community hold, and
-- what is the license-type mix inside each community?
--
-- The mart is one row per (community, license_type) that actually appears. Each row carries
-- the community total, the community's rank by that total, the type's share of the community,
-- and a flag marking the community's single most common type.

INSERT INTO license_density
WITH per_type AS (
    -- licenses of each type within each community
    SELECT
        community,
        license_type,
        count(*) AS type_count
    FROM clean_licenses
    GROUP BY community, license_type
),
per_community AS (
    -- total licenses per community
    SELECT
        community,
        sum(type_count) AS community_total_licenses
    FROM per_type
    GROUP BY community
),
ranked_community AS (
    -- rank communities by total licenses, busiest first; tied totals share a rank
    SELECT
        community,
        community_total_licenses,
        dense_rank() OVER (ORDER BY community_total_licenses DESC) AS community_rank
    FROM per_community
)
SELECT
    t.community,
    c.community_total_licenses,
    c.community_rank,
    t.license_type,
    t.type_count,
    -- type's share of its community's licenses, as a percentage to one decimal place
    round(t.type_count * 100.0 / c.community_total_licenses, 1) AS type_share_pct,
    -- 1 for the community's most common type; ties broken by license_type name
    CASE
        WHEN row_number() OVER (
            PARTITION BY t.community
            ORDER BY t.type_count DESC, t.license_type ASC
        ) = 1 THEN 1 ELSE 0
    END AS is_dominant_type
FROM per_type t
JOIN ranked_community c USING (community);
