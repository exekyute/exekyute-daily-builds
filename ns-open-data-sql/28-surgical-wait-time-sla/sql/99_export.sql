-- 99_export.sql
-- Write the golden result and the BI mart. Both carry an explicit total
-- ORDER BY ending in a unique key, so the files are byte-stable run to run.

COPY (
    SELECT
        section, rank, measure, zone, facility, procedure, period,
        year_quarter_index, value,
        surgery_rows, surgery_breaches, surgery_breach_pct,
        consult_rows, consult_breaches, consult_breach_pct,
        qoq_surgery_breach_pct, meets_min_rows,
        surgery_median, surgery_90th, surgery_tail_gap,
        consult_median, consult_90th, consult_tail_gap
    FROM wait_time_sla
    ORDER BY section_order, rank, facility, procedure, period
) TO 'out/wait_time_sla.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        period, year, quarter, year_quarter_index,
        zone, facility, procedure,
        consult_median, consult_90th, consult_tail_gap,
        surgery_median, surgery_90th, surgery_tail_gap,
        surgery_target_days, consult_target_days,
        surgery_measured, surgery_breach,
        consult_measured, consult_breach
    FROM mart_wait_times
    ORDER BY facility, procedure, year_quarter_index, period
) TO 'out/mart_wait_times.csv' (HEADER, DELIMITER ',');
