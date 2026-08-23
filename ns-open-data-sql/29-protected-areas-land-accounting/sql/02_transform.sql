-- 02_transform.sql
-- Typing, named constants, and the two organization-name rules. Nothing is
-- dropped here: the cleaned table has exactly as many rows as the snapshot,
-- and 03_analysis.sql asserts that in the coverage section.

-- ---------------------------------------------------------------------------
-- Named constants. Every number the analysis leans on that does not come out
-- of the snapshot is declared here and justified in spec.md.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE constants AS
SELECT
    -- Nova Scotia land area in hectares. 53,338 km2 of land (Statistics Canada,
    -- "Land and freshwater area, by province and territory") times 100 ha/km2.
    -- Land only; the province's 1,946 km2 of freshwater is deliberately out.
    CAST(5333800 AS DECIMAL(18, 2)) AS ns_land_area_ha,
    -- Hectares are rounded once, at the record level, to this many decimals so
    -- that every breakdown re-sums to the published grand total exactly.
    CAST(2 AS INTEGER)              AS hectare_rounding_dp,
    -- How many records the concentration curve lists row by row.
    CAST(25 AS INTEGER)             AS concentration_top_n,
    -- Milestones on the concentration curve, as fractions of total hectares.
    CAST(0.50 AS DECIMAL(5, 4))     AS half_share,
    CAST(0.90 AS DECIMAL(5, 4))     AS ninety_share,
    -- The status label that means the protection is in law rather than pending.
    'Designated'                    AS designated_status;

-- ---------------------------------------------------------------------------
-- Cleaning rules, named so the counts in the coverage section can point at them.
-- ---------------------------------------------------------------------------

-- Rule 1: trim, then collapse runs of whitespace to one space.
CREATE OR REPLACE MACRO squish(s) AS
    trim(regexp_replace(s, '\s+', ' ', 'g'));

-- Rule 2 and 3, applied to organization names only (owner, authority):
--   strip a leading "The ", then write the provincial department the short way.
-- Both spellings appear in the same snapshot for the same body, so this is a
-- spelling fix, not a merge of two different organizations. The rules run over
-- the whole string, so compound authorities are covered too.
CREATE OR REPLACE MACRO norm_org(s) AS
    regexp_replace(
        regexp_replace(squish(s), '^The ', ''),
        'Nova Scotia Environment and Climate Change',
        'NS Environment and Climate Change',
        'g'
    );

-- ---------------------------------------------------------------------------
-- Cleaned records. One row per published polygon record, same count as raw.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE protected_records AS
SELECT
    CAST(objectid AS BIGINT)                                   AS objectid,
    squish(pro_name)                                           AS area_name,
    squish(protect1)                                           AS designation,
    norm_org(authority)                                        AS authority,
    norm_org(owner)                                            AS owner,
    squish(status)                                             AS status,
    -- Hard CAST, not TRY_CAST: a hectare value that will not parse must fail
    -- the run rather than vanish into a NULL that quietly shrinks the total.
    CAST(round(CAST(ha_gis AS DECIMAL(18, 8)), 2) AS DECIMAL(18, 2)) AS hectares,
    CAST(ha_gis AS DECIMAL(18, 8))                             AS hectares_unrounded,
    -- stat_date is the source's designation year, published as a number.
    -- TRY_CAST here on purpose: a missing designation year is a reportable
    -- coverage fact (see the coverage section), not a reason to fail the run.
    TRY_CAST(nullif(squish(stat_date), '') AS INTEGER)         AS designation_year,
    -- Did the organization-name rules change anything on this row?
    CASE WHEN norm_org(authority) <> squish(authority) THEN 1 ELSE 0 END
                                                               AS authority_renamed,
    CASE WHEN norm_org(owner) <> squish(owner) THEN 1 ELSE 0 END
                                                               AS owner_renamed
FROM raw_protected;

-- ---------------------------------------------------------------------------
-- The concentration index. Records ordered largest first, ties broken by
-- objectid so the index is reproducible on any engine. This integer is the
-- ordered axis the BI running total walks, because the snapshot carries no
-- usable designation year (see spec.md).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE ranked_records AS
SELECT
    r.*,
    row_number() OVER (ORDER BY r.hectares DESC, r.objectid) AS record_rank
FROM protected_records AS r;

CREATE OR REPLACE TABLE cumulative_records AS
SELECT
    r.*,
    sum(r.hectares) OVER (
        ORDER BY r.record_rank
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_hectares
FROM ranked_records AS r;
