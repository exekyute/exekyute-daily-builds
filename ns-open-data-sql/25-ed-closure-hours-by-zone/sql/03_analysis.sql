-- 03_analysis.sql
-- Every figure the project reports is computed here. Each result set carries a
-- rank produced by an ORDER BY that ends in a unique tie-breaker, so the row
-- order does not depend on the engine, the version, or the scan order.

-- The reconciliation check the spec names: temporary plus scheduled must equal
-- the reported total on every row. This runs before any aggregation, because a
-- broken identity here would quietly poison every share below.
CREATE OR REPLACE TABLE recon_check AS
SELECT
    fiscal_year,
    fiscal_year_start,
    zone,
    facility_type,
    site,
    temporary_hours,
    scheduled_hours,
    total_hours,
    CAST(temporary_hours + scheduled_hours - total_hours AS DECIMAL(18,1)) AS recon_diff
FROM clean_closures;

CREATE OR REPLACE TABLE recon_summary AS
SELECT 1 AS ord, 'rows_checked' AS measure,
       CAST(count(*) AS BIGINT) AS row_count,
       CAST(NULL AS DECIMAL(18,1)) AS hours_value
FROM recon_check
UNION ALL
SELECT 2, 'rows_reconciled',
       CAST(count(*) FILTER (WHERE recon_diff = 0) AS BIGINT),
       CAST(NULL AS DECIMAL(18,1))
FROM recon_check
UNION ALL
SELECT 3, 'rows_mismatched',
       CAST(count(*) FILTER (WHERE recon_diff <> 0) AS BIGINT),
       CAST(NULL AS DECIMAL(18,1))
FROM recon_check
UNION ALL
SELECT 4, 'mismatch_total_abs_hours',
       CAST(NULL AS BIGINT),
       CAST(COALESCE(sum(abs(recon_diff)) FILTER (WHERE recon_diff <> 0), 0) AS DECIMAL(18,1))
FROM recon_check
UNION ALL
SELECT 5, 'mismatch_max_abs_hours',
       CAST(NULL AS BIGINT),
       CAST(COALESCE(max(abs(recon_diff)) FILTER (WHERE recon_diff <> 0), 0) AS DECIMAL(18,1))
FROM recon_check;

-- Provincial totals over the whole window. Every breakdown below re-sums to
-- the total_hours figure here.
CREATE OR REPLACE TABLE grand_total AS
SELECT
    CAST(count(*) AS BIGINT)                                     AS site_years,
    CAST(count(DISTINCT site) AS BIGINT)                         AS sites,
    CAST(count(DISTINCT fiscal_year_start) AS BIGINT)            AS fiscal_years,
    CAST(count(*) FILTER (WHERE total_hours = 0) AS BIGINT)      AS zero_site_years,
    CAST(sum(total_hours) AS DECIMAL(18,1))                      AS total_hours,
    CAST(sum(temporary_hours) AS DECIMAL(18,1))                  AS temporary_hours,
    CAST(sum(scheduled_hours) AS DECIMAL(18,1))                  AS scheduled_hours,
    temporary_share_pct(sum(temporary_hours), sum(total_hours))  AS temporary_share_pct
FROM clean_closures;

-- Closure hours by zone, all years combined.
CREATE OR REPLACE TABLE zone_totals AS
SELECT
    CAST(row_number() OVER (ORDER BY sum(total_hours) DESC, zone) AS INTEGER) AS rank,
    zone,
    CAST(count(*) AS BIGINT)                                    AS site_years,
    CAST(count(*) FILTER (WHERE total_hours = 0) AS BIGINT)     AS zero_site_years,
    CAST(sum(total_hours) AS DECIMAL(18,1))                     AS total_hours,
    CAST(sum(temporary_hours) AS DECIMAL(18,1))                 AS temporary_hours,
    CAST(sum(scheduled_hours) AS DECIMAL(18,1))                 AS scheduled_hours,
    temporary_share_pct(sum(temporary_hours), sum(total_hours)) AS temporary_share_pct
FROM clean_closures
GROUP BY zone;

-- Closure hours by facility type as reported in each site-year. A site that
-- was reclassified contributes its early years to the old type and its later
-- years to the new one, which is what the source rows actually say.
CREATE OR REPLACE TABLE type_totals AS
SELECT
    CAST(row_number() OVER (ORDER BY sum(total_hours) DESC, facility_type) AS INTEGER) AS rank,
    facility_type,
    CAST(count(*) AS BIGINT)                                    AS site_years,
    CAST(count(*) FILTER (WHERE total_hours = 0) AS BIGINT)     AS zero_site_years,
    CAST(sum(total_hours) AS DECIMAL(18,1))                     AS total_hours,
    CAST(sum(temporary_hours) AS DECIMAL(18,1))                 AS temporary_hours,
    CAST(sum(scheduled_hours) AS DECIMAL(18,1))                 AS scheduled_hours,
    temporary_share_pct(sum(temporary_hours), sum(total_hours)) AS temporary_share_pct
FROM clean_closures
GROUP BY facility_type;

-- Sites ranked by total closure hours, with each site's temporary share.
CREATE OR REPLACE TABLE site_totals AS
SELECT
    CAST(row_number() OVER (ORDER BY t.total_hours DESC, t.site) AS INTEGER) AS rank,
    t.site,
    p.zone,
    p.facility_type_latest,
    t.site_years,
    t.zero_site_years,
    t.total_hours,
    t.temporary_hours,
    t.scheduled_hours,
    t.temporary_share_pct
FROM (
    SELECT
        site,
        CAST(count(*) AS BIGINT)                                    AS site_years,
        CAST(count(*) FILTER (WHERE total_hours = 0) AS BIGINT)     AS zero_site_years,
        CAST(sum(total_hours) AS DECIMAL(18,1))                     AS total_hours,
        CAST(sum(temporary_hours) AS DECIMAL(18,1))                 AS temporary_hours,
        CAST(sum(scheduled_hours) AS DECIMAL(18,1))                 AS scheduled_hours,
        temporary_share_pct(sum(temporary_hours), sum(total_hours)) AS temporary_share_pct
    FROM clean_closures
    GROUP BY site
) AS t
JOIN site_profile AS p ON p.site = t.site;

-- Zone by fiscal year, with year-over-year change taken by LAG over
-- fiscal_year_start. Every zone reports in all twelve years, so the lag is
-- always the calendar-previous year; a zone's first year has no prior value
-- and its change fields stay blank.
CREATE OR REPLACE TABLE zone_year AS
WITH by_zone_year AS (
    SELECT
        zone,
        fiscal_year,
        fiscal_year_start,
        CAST(count(*) AS BIGINT)                                    AS site_years,
        CAST(count(*) FILTER (WHERE total_hours = 0) AS BIGINT)     AS zero_site_years,
        CAST(sum(total_hours) AS DECIMAL(18,1))                     AS total_hours,
        CAST(sum(temporary_hours) AS DECIMAL(18,1))                 AS temporary_hours,
        CAST(sum(scheduled_hours) AS DECIMAL(18,1))                 AS scheduled_hours,
        temporary_share_pct(sum(temporary_hours), sum(total_hours)) AS temporary_share_pct
    FROM clean_closures
    GROUP BY zone, fiscal_year, fiscal_year_start
),
with_lag AS (
    SELECT
        *,
        lag(total_hours) OVER (PARTITION BY zone ORDER BY fiscal_year_start) AS prev_total_hours
    FROM by_zone_year
)
SELECT
    CAST(row_number() OVER (ORDER BY zone, fiscal_year_start) AS INTEGER) AS rank,
    zone,
    fiscal_year,
    fiscal_year_start,
    site_years,
    zero_site_years,
    total_hours,
    temporary_hours,
    scheduled_hours,
    temporary_share_pct,
    CAST(total_hours - prev_total_hours AS DECIMAL(18,1))  AS yoy_change_hours,
    change_pct(total_hours, prev_total_hours)              AS yoy_change_pct
FROM with_lag;

-- Counts that describe the shape of the snapshot rather than its hours.
CREATE OR REPLACE TABLE shape_counts AS
SELECT
    CAST((SELECT count(*) FROM (SELECT site FROM clean_closures
                                GROUP BY site HAVING sum(total_hours) = 0)) AS BIGINT)
        AS sites_zero_all_years,
    CAST((SELECT count(*) FROM (SELECT site FROM clean_closures
                                GROUP BY site HAVING count(DISTINCT facility_type) > 1)) AS BIGINT)
        AS sites_type_changed,
    CAST((SELECT count(*) FROM (SELECT facility_type FROM clean_closures
                                GROUP BY facility_type HAVING sum(total_hours) > 0)) AS BIGINT)
        AS types_with_hours;

-- The sectioned result. Column meanings per section are in data_dictionary.md;
-- columns that do not apply to a section stay blank.
CREATE OR REPLACE TABLE ed_closures AS

-- Section 1: the provincial headline.
SELECT
    1 AS section_order, 'summary' AS section, 1 AS rank,
    'total_closure_hours' AS measure,
    CAST(NULL AS VARCHAR) AS fiscal_year, CAST(NULL AS INTEGER) AS fiscal_year_start,
    CAST(NULL AS VARCHAR) AS zone, CAST(NULL AS VARCHAR) AS facility_type,
    CAST(NULL AS VARCHAR) AS site,
    g.site_years, g.zero_site_years,
    g.total_hours, g.temporary_hours, g.scheduled_hours, g.temporary_share_pct,
    CAST(NULL AS DECIMAL(18,1)) AS yoy_change_hours,
    CAST(NULL AS DECIMAL(9,2)) AS yoy_change_pct
FROM grand_total AS g

UNION ALL SELECT 1, 'summary', 2, 'sites_observed',
    NULL, NULL, NULL, NULL, NULL,
    g.sites, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM grand_total AS g

UNION ALL SELECT 1, 'summary', 3, 'fiscal_years_observed',
    NULL, NULL, NULL, NULL, NULL,
    g.fiscal_years, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM grand_total AS g

UNION ALL SELECT 1, 'summary', 4, 'site_years_with_zero_closure_hours',
    NULL, NULL, NULL, NULL, NULL,
    g.zero_site_years, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM grand_total AS g

UNION ALL SELECT 1, 'summary', 5, 'sites_with_zero_closure_hours_all_years',
    NULL, NULL, NULL, NULL, NULL,
    s.sites_zero_all_years, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM shape_counts AS s

UNION ALL SELECT 1, 'summary', 6, 'sites_with_facility_type_change',
    NULL, NULL, NULL, NULL, NULL,
    s.sites_type_changed, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM shape_counts AS s

UNION ALL SELECT 1, 'summary', 7, 'facility_types_with_any_closure_hours',
    NULL, NULL, NULL, NULL, NULL,
    s.types_with_hours, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM shape_counts AS s

UNION ALL SELECT 1, 'summary', 8, 'site_years_with_undefined_temporary_share',
    NULL, NULL, NULL, NULL, NULL,
    g.zero_site_years, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM grand_total AS g

-- Section 2: the row ledger. Snapshot rows minus the exclusion classes equals
-- the clean row count.
UNION ALL SELECT 2, 'row_accounting', CAST(ra.ord AS INTEGER), ra.measure,
    NULL, NULL, NULL, NULL, NULL,
    ra.row_count, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM row_accounting AS ra

-- Section 3: the temporary plus scheduled equals total check.
UNION ALL SELECT 3, 'reconciliation', CAST(rs.ord AS INTEGER), rs.measure,
    NULL, NULL, NULL, NULL, NULL,
    rs.row_count, NULL, rs.hours_value, NULL, NULL, NULL, NULL, NULL
FROM recon_summary AS rs

-- Section 4: closure hours by zone.
UNION ALL SELECT 4, 'zone_totals', z.rank, NULL,
    NULL, NULL, z.zone, NULL, NULL,
    z.site_years, z.zero_site_years,
    z.total_hours, z.temporary_hours, z.scheduled_hours, z.temporary_share_pct,
    NULL, NULL
FROM zone_totals AS z

-- Section 5: closure hours by facility type.
UNION ALL SELECT 5, 'type_totals', ty.rank, NULL,
    NULL, NULL, NULL, ty.facility_type, NULL,
    ty.site_years, ty.zero_site_years,
    ty.total_hours, ty.temporary_hours, ty.scheduled_hours, ty.temporary_share_pct,
    NULL, NULL
FROM type_totals AS ty

-- Section 6: zone by fiscal year, with year-over-year change.
UNION ALL SELECT 6, 'zone_year', zy.rank, NULL,
    zy.fiscal_year, zy.fiscal_year_start, zy.zone, NULL, NULL,
    zy.site_years, zy.zero_site_years,
    zy.total_hours, zy.temporary_hours, zy.scheduled_hours, zy.temporary_share_pct,
    zy.yoy_change_hours, zy.yoy_change_pct
FROM zone_year AS zy

-- Section 7: sites ranked by total closure hours.
UNION ALL SELECT 7, 'site_totals', st.rank, NULL,
    NULL, NULL, st.zone, st.facility_type_latest, st.site,
    st.site_years, st.zero_site_years,
    st.total_hours, st.temporary_hours, st.scheduled_hours, st.temporary_share_pct,
    NULL, NULL
FROM site_totals AS st;

-- The BI mart: one cleaned row per source site-year, 456 rows, summing to the
-- same provincial total the golden file proves.
CREATE OR REPLACE TABLE mart_ed_closures AS
SELECT
    fiscal_year,
    fiscal_year_start,
    zone,
    facility_type,
    site,
    temporary_hours,
    scheduled_hours,
    total_hours,
    CAST(CASE WHEN total_hours = 0 THEN 1 ELSE 0 END AS INTEGER) AS is_zero_closure
FROM clean_closures;

-- The lines run.py prints after a run. Building them here keeps the driver
-- free of any figure of its own.
CREATE OR REPLACE TABLE headline AS
SELECT 1 AS ord,
       'Total closure hours 2012-13 to 2023-24: '
       || format('{:,.1f}', CAST(total_hours AS DOUBLE)) AS line
FROM grand_total
UNION ALL
SELECT 2,
       'Temporary ' || format('{:,.1f}', CAST(temporary_hours AS DOUBLE))
       || ' hours (' || CAST(temporary_share_pct AS VARCHAR) || '%), scheduled '
       || format('{:,.1f}', CAST(scheduled_hours AS DOUBLE)) || ' hours'
FROM grand_total
UNION ALL
SELECT 3,
       CAST(sites AS VARCHAR) || ' sites across ' || CAST(fiscal_years AS VARCHAR)
       || ' fiscal years, ' || CAST(site_years AS VARCHAR) || ' site-years, '
       || CAST(zero_site_years AS VARCHAR) || ' of them with zero closure hours'
FROM grand_total;
