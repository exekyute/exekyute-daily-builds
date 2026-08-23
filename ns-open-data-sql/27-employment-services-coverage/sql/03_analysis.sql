-- 03_analysis.sql
-- Every result table here ends in a total ORDER BY whose last term is unique,
-- so row order is reproducible across DuckDB versions and machines. Ranks are
-- assigned by ROW_NUMBER over an ordering that already ends in a unique key,
-- never by a sort on the measure alone: with five regions and a real tie at
-- the top (two regions hold 12 centres each), a measure-only sort would be
-- ambiguous.

-- The denominator every share divides by.
CREATE OR REPLACE TABLE grand AS
SELECT count(*) AS total_centres FROM centre_scored;

-- ---------------------------------------------------------------------------
-- Coverage by declared region
-- ---------------------------------------------------------------------------
-- LEFT JOIN from the declared universe onto the observed centres, so a region
-- in REGION_UNIVERSE with no centres in the snapshot appears with centres = 0
-- rather than vanishing from the result.
CREATE OR REPLACE TABLE region_coverage AS
SELECT
    ROW_NUMBER() OVER (ORDER BY count(c.region) DESC, u.region) AS rank,
    u.region,
    count(c.region)                          AS centres,
    count(DISTINCT c.city_town)              AS towns,
    count(DISTINCT c.center_name)            AS providers,
    CAST(ROUND(100.0 * count(c.region) / (SELECT total_centres FROM grand), 2)
         AS DECIMAL(6,2))                    AS share_pct
FROM const_region_universe u
LEFT JOIN centre_scored c ON c.region = u.region
GROUP BY u.region
ORDER BY centres DESC, u.region;

-- ---------------------------------------------------------------------------
-- Coverage by city or town
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE city_coverage AS
SELECT
    ROW_NUMBER() OVER (ORDER BY count(*) DESC, region, city_town) AS rank,
    region,
    city_town,
    count(*)                                 AS centres,
    count(DISTINCT center_name)              AS providers,
    CAST(ROUND(100.0 * count(*) / (SELECT total_centres FROM grand), 2)
         AS DECIMAL(6,2))                    AS share_pct
FROM centre_scored
GROUP BY region, city_town
ORDER BY centres DESC, region, city_town;

-- ---------------------------------------------------------------------------
-- Coverage by FSA (forward sortation area, the first three postal characters)
-- ---------------------------------------------------------------------------
-- Centres with a blank or malformed postal code carry fsa = NULL and are
-- reported as their own row here rather than dropped, so the centre counts in
-- this section always re-sum to the grand total.
CREATE OR REPLACE TABLE fsa_coverage AS
SELECT
    ROW_NUMBER() OVER (ORDER BY count(*) DESC, coalesce(fsa, 'ZZZ')) AS rank,
    fsa,
    count(*)                                 AS centres,
    count(DISTINCT city_town)                AS towns,
    CAST(ROUND(100.0 * count(*) / (SELECT total_centres FROM grand), 2)
         AS DECIMAL(6,2))                    AS share_pct
FROM centre_scored
GROUP BY fsa
ORDER BY centres DESC, coalesce(fsa, 'ZZZ');

-- ---------------------------------------------------------------------------
-- Contact-channel completeness
-- ---------------------------------------------------------------------------
-- Driven by the declared CONTACT_CHANNELS list, so a channel carried by no
-- centre still reports as a zero row.
CREATE OR REPLACE TABLE contact_completeness AS
WITH channel_flag AS (
    SELECT 'email'    AS channel, has_email    AS present FROM centre_scored
    UNION ALL
    SELECT 'web',                 has_web              FROM centre_scored
    UNION ALL
    SELECT 'facebook',            has_facebook         FROM centre_scored
    UNION ALL
    SELECT 'twitter',             has_twitter          FROM centre_scored
)
SELECT
    k.channel_ord                            AS rank,
    k.channel,
    coalesce(sum(f.present), 0)              AS centres,
    CAST(ROUND(100.0 * coalesce(sum(f.present), 0)
               / (SELECT total_centres FROM grand), 2)
         AS DECIMAL(6,2))                    AS share_pct
FROM const_contact_channel k
LEFT JOIN channel_flag f ON f.channel = k.channel
GROUP BY k.channel_ord, k.channel
ORDER BY k.channel_ord;

-- ---------------------------------------------------------------------------
-- Exclusion classes
-- ---------------------------------------------------------------------------
-- No row is ever dropped from the pipeline. Each class below counts the rows
-- that would have been dropped by a less careful build, and every class is
-- reported even when its count is zero.
CREATE OR REPLACE TABLE exclusions AS
SELECT 1 AS rank, 'region_not_in_universe'  AS measure,
       sum(flag_region_not_in_universe)     AS centres FROM centre_scored
UNION ALL
SELECT 2, 'postal_code_blank',      sum(flag_postal_blank)      FROM centre_scored
UNION ALL
SELECT 3, 'postal_code_malformed',  sum(flag_postal_malformed)  FROM centre_scored
UNION ALL
SELECT 4, 'coordinate_out_of_bounds', sum(flag_coord_out_of_bounds) FROM centre_scored
ORDER BY rank;

-- ---------------------------------------------------------------------------
-- Headline summary
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE summary AS
SELECT  1 AS rank, 'total_centres' AS measure, NULL AS region,
        (SELECT total_centres FROM grand) AS centres
UNION ALL
SELECT  2, 'declared_regions', NULL, (SELECT count(*) FROM const_region_universe)
UNION ALL
SELECT  3, 'regions_with_centres', NULL,
        (SELECT count(*) FROM region_coverage WHERE centres > 0)
UNION ALL
SELECT  4, 'regions_with_zero_centres', NULL,
        (SELECT count(*) FROM region_coverage WHERE centres = 0)
UNION ALL
SELECT  5, 'distinct_towns', NULL,
        (SELECT count(DISTINCT city_town) FROM centre_scored)
UNION ALL
SELECT  6, 'distinct_fsas', NULL,
        (SELECT count(DISTINCT fsa) FROM centre_scored)
UNION ALL
SELECT  7, 'distinct_providers', NULL,
        (SELECT count(DISTINCT center_name) FROM centre_scored)
UNION ALL
SELECT  8, 'top_region_centres',
        (SELECT region FROM region_coverage WHERE rank = 1),
        (SELECT centres FROM region_coverage WHERE rank = 1)
UNION ALL
SELECT  9, 'centres_with_all_channels', NULL,
        (SELECT count(*) FROM centre_scored WHERE contact_channels = 4)
UNION ALL
SELECT 10, 'centres_flagged_total', NULL,
        (SELECT count(*) FROM centre_scored
          WHERE flag_region_not_in_universe + flag_postal_blank
              + flag_postal_malformed + flag_coord_out_of_bounds > 0)
ORDER BY rank;

-- ---------------------------------------------------------------------------
-- The six sections stacked into the golden result
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE services_coverage AS
SELECT 1 AS section_order, 'summary' AS section, rank, measure,
       region, NULL AS city_town, NULL AS fsa,
       CAST(centres AS BIGINT) AS centres,
       CAST(NULL AS BIGINT) AS towns, CAST(NULL AS BIGINT) AS providers,
       CAST(NULL AS DECIMAL(6,2)) AS share_pct
FROM summary
UNION ALL
SELECT 2, 'exclusions', rank, measure,
       NULL, NULL, NULL, CAST(centres AS BIGINT), NULL, NULL, NULL
FROM exclusions
UNION ALL
SELECT 3, 'region_coverage', rank, NULL,
       region, NULL, NULL, CAST(centres AS BIGINT),
       CAST(towns AS BIGINT), CAST(providers AS BIGINT), share_pct
FROM region_coverage
UNION ALL
SELECT 4, 'city_coverage', rank, NULL,
       region, city_town, NULL, CAST(centres AS BIGINT),
       NULL, CAST(providers AS BIGINT), share_pct
FROM city_coverage
UNION ALL
SELECT 5, 'fsa_coverage', rank, NULL,
       NULL, NULL, fsa, CAST(centres AS BIGINT),
       CAST(towns AS BIGINT), NULL, share_pct
FROM fsa_coverage
UNION ALL
SELECT 6, 'contact_completeness', rank, channel,
       NULL, NULL, NULL, CAST(centres AS BIGINT), NULL, NULL, share_pct
FROM contact_completeness;

-- ---------------------------------------------------------------------------
-- The BI mart: one row per centre, latitude and longitude named correctly
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE mart_services AS
SELECT
    c.region,
    c.center_name,
    c.city_town,
    c.street_address,
    c.postal_code,
    c.fsa,
    c.latitude,
    c.longitude,
    c.phone,
    c.email,
    c.web,
    c.facebook,
    c.twitter,
    c.has_email,
    c.has_web,
    c.has_facebook,
    c.has_twitter,
    c.contact_channels,
    r.centres    AS region_centres,
    r.share_pct  AS region_share_pct
FROM centre_scored c
LEFT JOIN region_coverage r ON r.region = c.region;
