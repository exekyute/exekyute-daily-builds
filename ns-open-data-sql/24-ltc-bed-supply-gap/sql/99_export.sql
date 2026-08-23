-- 99_export: write the golden result, the long-form BI mart, and the print table.
-- Every COPY ends in a total ORDER BY whose last term is unique, so the files are
-- byte-for-byte reproducible on any DuckDB build.

-- Golden result. (section_ord, ord) is unique across the whole table.
COPY (
    SELECT
        section,
        ord,
        measure,
        zone,
        facility_type,
        bed_type,
        facility_id,
        facility_name,
        town,
        facilities,
        beds,
        share_pct,
        avg_beds,
        median_beds
    FROM ltc_bed_supply
    ORDER BY section_ord, ord
) TO 'out/ltc_bed_supply.csv' (HEADER, DELIMITER ',');

-- BI mart, long form: one row per facility per bed type, so a zone-by-bed-type
-- matrix is a group-by rather than a pivot. facility_total_beds repeats down a
-- facility's four rows and must never be summed; sum beds where is_core_bed = 1.
-- (facility_id, bed_type) is unique.
COPY (
    SELECT
        l.facility_id,
        l.facility_name,
        l.town,
        l.postal_code,
        l.zone,
        l.facility_type,
        l.sea_participating,
        l.longitude,
        l.latitude,
        f.total_beds AS facility_total_beds,
        l.bed_type,
        l.is_core_bed,
        l.beds
    FROM facility_bed_long l
    JOIN facility_totals f USING (facility_id)
    ORDER BY l.facility_id, l.bed_type
) TO 'out/mart_ltc.csv' (HEADER, DELIMITER ',');

-- The table `python run.py show` prints. ord is unique.
COPY (
    SELECT
        zone,
        facilities,
        nursing_beds,
        residential_beds,
        total_beds,
        share_pct,
        avg_beds,
        median_beds,
        nursing_respite_beds,
        residential_respite_beds
    FROM show_beds_by_zone
    ORDER BY ord
) TO 'out/show_beds_by_zone.csv' (HEADER, DELIMITER ',');
