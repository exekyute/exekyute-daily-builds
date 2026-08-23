-- 02_transform.sql
-- Cleaning rules, all deterministic and all named here rather than buried in
-- the analysis:
--
--   * tidy()      trim, then collapse runs of spaces
--   * label_key() the tidy form lowercased; two labels that differ only in
--                 case or spacing share a key and therefore group together
--   * money       nsbi_financial_contribution is cast to DECIMAL(18,2). A
--                 blank becomes NULL through NULLIF and is never coerced to
--                 zero; a value that is neither blank nor numeric fails the
--                 cast and stops the run.
--   * counties    the Halifax family of labels folds onto the single county
--                 name 'Halifax' (named constant COUNTY_HALIFAX_VARIANTS).
--                 Nova Scotia has one Halifax county, and the urban, rural,
--                 and regional-municipality qualifiers describe the same
--                 county boundary, so the fold is a lookup onto the province's
--                 fixed 18-county vocabulary, not a judgment call.
--   * sectors and deal types get case and spacing folding only. Abbreviation
--     and longhand pairs such as 'BDP' and 'Business Development Program'
--     stay distinct: expanding them needs a program crosswalk that neither
--     this dataset nor the portal publishes, and the labels change with the
--     fiscal year, which is itself a finding worth keeping visible.
--   * coordinates latitude and longitude are cast from their own columns. A
--     blank leaves the row not mappable and counted, never guessed at. A pair
--     that lands outside the Nova Scotia rectangle (named constant NS_BOUNDS)
--     is flagged rather than corrected, so a point map can leave it out on
--     purpose and still report how many it left out.

CREATE OR REPLACE MACRO tidy(x) AS
    regexp_replace(trim(CAST(x AS VARCHAR)), ' +', ' ', 'g');

CREATE OR REPLACE MACRO label_key(x) AS
    lower(tidy(x));

-- NAMED CONSTANT: COUNTY_HALIFAX_VARIANTS
-- Every county label, keyed, that means Halifax County.
CREATE OR REPLACE TABLE county_halifax_variants (variant VARCHAR);
INSERT INTO county_halifax_variants VALUES
    ('halifax'),
    ('halifax (urban)'),
    ('halifax (rural)'),
    ('halifax regional municipality');

-- NAMED CONSTANT: COUNTY_HALIFAX_CANONICAL
-- The single spelling those variants fold onto.
CREATE OR REPLACE TABLE county_halifax_canonical (canonical VARCHAR);
INSERT INTO county_halifax_canonical VALUES ('Halifax');

-- NAMED CONSTANT: COUNTY_NON_GEOGRAPHIC_LABELS
-- County-column values that do not name a county. They stay in the data and
-- in the money totals; they are flagged so the map and the geographic
-- breakdown can report them as their own class instead of dropping them.
CREATE OR REPLACE TABLE county_non_geographic_labels (variant VARCHAR);
INSERT INTO county_non_geographic_labels VALUES
    ('not applicable / unknown'),
    ('province-wide');

-- NAMED CONSTANT: TOP_RECIPIENTS_N
-- How many accounts the top-recipients section lists.
CREATE OR REPLACE TABLE top_recipients_n (n INTEGER);
INSERT INTO top_recipients_n VALUES (25);

-- NAMED CONSTANT: NS_BOUNDS
-- A generous rectangle around Nova Scotia. It is drawn wide on purpose: the
-- job is to catch a coordinate that is plainly somewhere else, not to trim
-- points near the coastline.
CREATE OR REPLACE TABLE ns_bounds (
    lat_min DOUBLE, lat_max DOUBLE, lon_min DOUBLE, lon_max DOUBLE
);
INSERT INTO ns_bounds VALUES (43.0, 47.5, -67.0, -59.0);

CREATE OR REPLACE TABLE clean_deals AS
WITH typed AS (
SELECT
    CAST(tidy(object_id_) AS INTEGER) AS object_id,

    tidy(account_name)      AS account_raw,
    label_key(account_name) AS account_key,

    tidy(nsbi_sector)       AS sector_raw,
    label_key(nsbi_sector)  AS sector_key,

    tidy(deal_type)         AS deal_type_raw,
    label_key(deal_type)    AS deal_type_key,

    CASE
        WHEN label_key(nsbi_county) IN (SELECT variant FROM county_halifax_variants)
        THEN (SELECT lower(canonical) FROM county_halifax_canonical)
        ELSE label_key(nsbi_county)
    END AS county_key,
    CASE
        WHEN label_key(nsbi_county) IN (SELECT variant FROM county_halifax_variants)
        THEN (SELECT canonical FROM county_halifax_canonical)
        ELSE tidy(nsbi_county)
    END AS county_raw,
    CASE
        WHEN label_key(nsbi_county) IN (SELECT variant FROM county_non_geographic_labels)
        THEN FALSE ELSE TRUE
    END AS county_is_geographic,

    -- Blank rule: NULLIF turns a blank into NULL, which sum() skips and which
    -- share-of-total denominators therefore never see. Zero stays zero.
    NULLIF(tidy(nsbi_financial_contribution), '') IS NOT NULL AS has_contribution,
    CAST(NULLIF(tidy(nsbi_financial_contribution), '') AS DECIMAL(18,2)) AS contribution,

    tidy(place_name) AS place_name,
    tidy(postalcode) AS postalcode,

    tidy(fiscal_year) AS fiscal_year,
    CAST(substr(tidy(fiscal_year), 1, 4) AS INTEGER) AS fy_start,

    CAST(NULLIF(tidy(latitude), '')  AS DOUBLE) AS latitude,
    CAST(NULLIF(tidy(longitude), '') AS DOUBLE) AS longitude
FROM raw_deals
)
SELECT
    typed.*,
    (latitude IS NOT NULL AND longitude IS NOT NULL) AS is_mappable,
    COALESCE(
        latitude  BETWEEN (SELECT lat_min FROM ns_bounds)
                      AND (SELECT lat_max FROM ns_bounds)
        AND longitude BETWEEN (SELECT lon_min FROM ns_bounds)
                          AND (SELECT lon_max FROM ns_bounds),
        FALSE) AS in_ns_bounds
FROM typed;

-- One display spelling per key: the most frequent raw spelling wins, and
-- alphabetical order breaks ties, so the label never depends on scan order.

CREATE OR REPLACE TABLE sector_display AS
SELECT sector_key, sector_raw AS nsbi_sector
FROM (
    SELECT sector_key, sector_raw,
           row_number() OVER (PARTITION BY sector_key
                              ORDER BY count(*) DESC, sector_raw) AS rn
    FROM clean_deals
    GROUP BY sector_key, sector_raw
)
WHERE rn = 1;

CREATE OR REPLACE TABLE deal_type_display AS
SELECT deal_type_key, deal_type_raw AS deal_type
FROM (
    SELECT deal_type_key, deal_type_raw,
           row_number() OVER (PARTITION BY deal_type_key
                              ORDER BY count(*) DESC, deal_type_raw) AS rn
    FROM clean_deals
    GROUP BY deal_type_key, deal_type_raw
)
WHERE rn = 1;

CREATE OR REPLACE TABLE county_display AS
SELECT county_key, county_raw AS nsbi_county, county_is_geographic
FROM (
    SELECT county_key, county_raw, county_is_geographic,
           row_number() OVER (PARTITION BY county_key
                              ORDER BY count(*) DESC, county_raw) AS rn
    FROM clean_deals
    GROUP BY county_key, county_raw, county_is_geographic
)
WHERE rn = 1;

CREATE OR REPLACE TABLE account_display AS
SELECT account_key, account_raw AS account_name
FROM (
    SELECT account_key, account_raw,
           row_number() OVER (PARTITION BY account_key
                              ORDER BY count(*) DESC, account_raw) AS rn
    FROM clean_deals
    GROUP BY account_key, account_raw
)
WHERE rn = 1;
