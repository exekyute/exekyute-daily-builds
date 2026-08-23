-- 02_transform: type the raw text, classify every row, and reshape the four bed
-- columns into one long table.
--
-- Coordinate traps in this source, handled once here:
--   x_coordinate is LONGITUDE and y_coordinate is LATITUDE, despite the names.
--   the_geom is a POINT in a projected coordinate system, not lat/long, so it is
--     never read.
--   location holds embedded newlines and a pre-formatted "(lat, long)" string, so
--     it is never parsed; longitude and latitude come from the two numeric columns.

CREATE OR REPLACE TABLE ltc_typed AS
SELECT
    TRIM(r.facility_id)                                 AS facility_id,
    TRIM(r.facility_name)                               AS facility_name,
    TRIM(r.address)                                     AS address,
    TRIM(r.town)                                        AS town,
    TRIM(r.postal_code)                                 AS postal_code,
    TRIM(r.facility_type)                               AS facility_type,
    TRIM(r.zone)                                        AS zone,
    TRIM(r.single_entry_access_sea_participating)       AS sea_participating,
    TRY_CAST(r.x_coordinate AS DOUBLE)                  AS longitude,
    TRY_CAST(r.y_coordinate AS DOUBLE)                  AS latitude,
    TRY_CAST(r.nursing_homes_nh_no_of_beds AS DOUBLE)                AS nursing_raw,
    TRY_CAST(r.residential_care_facilities_rcf_no_of_beds AS DOUBLE) AS residential_raw,
    TRY_CAST(r.nursing_homes_nh_no_of_respite_beds AS DOUBLE)        AS nursing_respite_raw,
    TRY_CAST(r.rcf_respite_beds AS DOUBLE)                           AS residential_respite_raw,
    COUNT(*) OVER (PARTITION BY TRIM(r.facility_id))    AS id_occurrences
FROM ltc_raw r;

-- Exclusion classes, checked in a fixed order so a row lands in exactly one.
-- Nothing is dropped without a class and a count.
CREATE OR REPLACE TABLE ltc_classified AS
SELECT
    t.*,
    CASE
        WHEN t.facility_id IS NULL OR t.facility_id = ''
            THEN 'excluded_missing_facility_id'
        WHEN t.id_occurrences > 1
            THEN 'excluded_duplicate_facility_id'
        WHEN t.nursing_raw IS NULL OR t.residential_raw IS NULL
          OR t.nursing_respite_raw IS NULL OR t.residential_respite_raw IS NULL
            THEN 'excluded_non_numeric_beds'
        WHEN t.nursing_raw < 0 OR t.residential_raw < 0
          OR t.nursing_respite_raw < 0 OR t.residential_respite_raw < 0
            THEN 'excluded_negative_beds'
        WHEN t.nursing_raw <> FLOOR(t.nursing_raw)
          OR t.residential_raw <> FLOOR(t.residential_raw)
          OR t.nursing_respite_raw <> FLOOR(t.nursing_respite_raw)
          OR t.residential_respite_raw <> FLOOR(t.residential_respite_raw)
            THEN 'excluded_fractional_beds'
        WHEN t.zone NOT IN (SELECT zone FROM zone_dim)
            THEN 'excluded_unknown_zone'
        ELSE 'kept'
    END AS row_class
FROM ltc_typed t;

-- The analysis table: one row per kept facility, bed counts as integers.
CREATE OR REPLACE TABLE ltc_facility AS
SELECT
    c.facility_id,
    c.facility_name,
    c.address,
    c.town,
    c.postal_code,
    c.facility_type,
    c.zone,
    c.sea_participating,
    c.longitude,
    c.latitude,
    CAST(c.nursing_raw             AS INTEGER) AS nursing_beds,
    CAST(c.residential_raw         AS INTEGER) AS residential_beds,
    CAST(c.nursing_respite_raw     AS INTEGER) AS nursing_respite_beds,
    CAST(c.residential_respite_raw AS INTEGER) AS residential_respite_beds
FROM ltc_classified c
WHERE c.row_class = 'kept';

-- One row per facility per bed type. 4 bed types x every kept facility, so the
-- zone-by-bed-type view is a plain group-by rather than a pivot.
CREATE OR REPLACE TABLE facility_bed_long AS
SELECT
    f.facility_id,
    f.facility_name,
    f.town,
    f.postal_code,
    f.zone,
    f.facility_type,
    f.sea_participating,
    f.longitude,
    f.latitude,
    d.bed_type_ord,
    d.bed_type,
    d.is_core_bed,
    CASE d.bed_type
        WHEN 'nursing'             THEN f.nursing_beds
        WHEN 'residential'         THEN f.residential_beds
        WHEN 'nursing_respite'     THEN f.nursing_respite_beds
        WHEN 'residential_respite' THEN f.residential_respite_beds
    END AS beds
FROM ltc_facility f
CROSS JOIN bed_type_dim d;
