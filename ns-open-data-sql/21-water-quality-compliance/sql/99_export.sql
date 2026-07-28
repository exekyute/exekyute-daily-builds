-- 99_export.sql
-- Write the compliance result and the BI mart. Both exports carry an
-- explicit total ORDER BY that ends on a unique column, so the files are
-- byte-stable run to run regardless of engine version or thread count.

COPY (
    SELECT
        section, rank, measure, analyte, location_id, location,
        direction, threshold, guideline_unit,
        n_samples, n_passing, pass_pct, n_non_detect, nondetect_pct,
        n_censored_above,
        first_sample_date, last_sample_date, days_since_last_sample
    FROM water_compliance
    ORDER BY section_order, rank
) TO 'out/water_compliance.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        sample_date, sample_time, sample_year, location_id, location,
        analyte, sample_fraction, result_unit, result_value,
        guideline_unit, guideline_threshold, guideline_direction,
        row_class, is_evaluated, is_pass, is_non_detect, is_censored_above
    FROM mart_water
    ORDER BY location_id, analyte, sample_fraction, sample_date, sample_time
) TO 'out/mart_water.csv' (HEADER, DELIMITER ',');
