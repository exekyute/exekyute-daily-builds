-- 02_transform.sql
-- One cleaned row per centre. Nothing is filtered out here: every row that
-- entered raw_centres leaves this file, carrying flags that say what is wrong
-- with it. 03_analysis.sql counts those flags as named exclusion classes.
--
-- THE COORDINATE TRAP. In this dataset the column named x_coordinate holds
-- LATITUDE (values near 45) and the column named y_coordinate holds LONGITUDE
-- (values near -62). That is the reverse of the usual x=longitude convention
-- and the reverse of the other Nova Scotia geographic datasets. The source's
-- own location_1 field settles it: on all 47 rows location_1 reads exactly
-- '(x_coordinate, y_coordinate)', and a Socrata location literal is written
-- (latitude, longitude). This file swaps the names once, here, and every
-- downstream table and export uses latitude and longitude by those names so
-- the mapping cannot be misread again.

CREATE OR REPLACE TABLE centre AS
SELECT
    trim(r.region)                                   AS region,
    trim(r.center_name)                              AS center_name,
    trim(r.street_address)                           AS street_address,
    trim(r.city_town)                                AS city_town,
    upper(trim(r.postal_code))                       AS postal_code,
    trim(r.phone)                                    AS phone,

    -- FSA: the first three characters of the postal code, uppercased.
    -- A forward sortation area is three characters (B3J), not one letter.
    CASE
        WHEN trim(coalesce(r.postal_code, '')) = '' THEN NULL
        ELSE upper(substr(trim(r.postal_code), 1, k.fsa_length))
    END                                              AS fsa,

    -- The rename. x_coordinate is latitude, y_coordinate is longitude.
    try_cast(trim(r.x_coordinate) AS DOUBLE)         AS latitude,
    try_cast(trim(r.y_coordinate) AS DOUBLE)         AS longitude,

    nullif(trim(coalesce(r.email, '')), '')          AS email,
    nullif(trim(coalesce(r.web, '')), '')            AS web,
    nullif(trim(coalesce(r.facebook, '')), '')       AS facebook,
    nullif(trim(coalesce(r.twitter, '')), '')        AS twitter,

    -- Contact-channel flags. A channel counts as carried when the field holds
    -- a non-blank value; the pipeline does not dial the number or open the URL,
    -- so "carried" means published, not verified reachable.
    CASE WHEN nullif(trim(coalesce(r.email, '')), '')    IS NOT NULL THEN 1 ELSE 0 END AS has_email,
    CASE WHEN nullif(trim(coalesce(r.web, '')), '')      IS NOT NULL THEN 1 ELSE 0 END AS has_web,
    CASE WHEN nullif(trim(coalesce(r.facebook, '')), '') IS NOT NULL THEN 1 ELSE 0 END AS has_facebook,
    CASE WHEN nullif(trim(coalesce(r.twitter, '')), '')  IS NOT NULL THEN 1 ELSE 0 END AS has_twitter,

    -- Exclusion-class flags. Counted and reported, never used to drop a row.
    CASE WHEN u.region IS NULL THEN 1 ELSE 0 END     AS flag_region_not_in_universe,
    CASE WHEN trim(coalesce(r.postal_code, '')) = '' THEN 1 ELSE 0 END
                                                     AS flag_postal_blank,
    CASE
        WHEN trim(coalesce(r.postal_code, '')) = '' THEN 0
        WHEN regexp_matches(
                upper(substr(trim(r.postal_code), 1, k.fsa_length)),
                k.fsa_pattern) THEN 0
        ELSE 1
    END                                              AS flag_postal_malformed,
    CASE
        WHEN try_cast(trim(r.x_coordinate) AS DOUBLE) BETWEEN k.lat_min AND k.lat_max
         AND try_cast(trim(r.y_coordinate) AS DOUBLE) BETWEEN k.lon_min AND k.lon_max
        THEN 0 ELSE 1
    END                                              AS flag_coord_out_of_bounds
FROM raw_centres r
CROSS JOIN const_rules k
LEFT JOIN const_region_universe u
       ON u.region = trim(r.region);

-- Channel count per centre, kept separate so the flag definitions above stay
-- the single source of the four channel rules.
CREATE OR REPLACE TABLE centre_scored AS
SELECT
    c.*,
    c.has_email + c.has_web + c.has_facebook + c.has_twitter AS contact_channels
FROM centre c;
