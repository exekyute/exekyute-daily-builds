-- 99_export.sql
-- Write the audit result and the BI mart. Both exports carry a total
-- ORDER BY ending in a unique tie-breaker, so the files are byte-stable run
-- to run regardless of engine version or scan order. Completeness
-- percentages tie constantly, so no export sorts on a measure alone.

COPY (
    SELECT
        section, rank, site_id, reading_date, measure, detail,
        cadence_seconds, seconds, readings_actual, slots_covered,
        readings_expected, uptime_pct, share_pct, gap_count,
        frozen_run_count, out_of_range_count, missing_values
    FROM station_quality
    ORDER BY section_order, rank, site_id, reading_date
) TO 'out/station_quality.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        site_id, reading_date, cadence_seconds,
        readings_actual, readings_expected, slots_covered, surplus_readings,
        uptime_pct, gap_count, frozen_run_count, out_of_range_count,
        missing_air_temperature, missing_relative_humidity,
        missing_avg_wind_speed, missing_values,
        station_completeness_rank, station_uptime_pct,
        station_readings_actual, station_readings_expected,
        station_gap_count, station_frozen_run_count,
        station_out_of_range_count, station_missing_values,
        station_days_with_no_readings, station_flag, station_flag_reasons
    FROM mart_station_quality
    ORDER BY site_id, reading_date
) TO 'out/mart_station_quality.csv' (HEADER, DELIMITER ',');
