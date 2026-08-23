-- 01_load.sql
-- Load the pinned snapshot. The filename carries the pull date; replacing the
-- snapshot means re-baselining expected/station_quality.csv on purpose.

INSERT INTO raw_readings
SELECT site_id, datetimeutc, air_temperature, relative_humidity, avg_wind_speed
FROM read_csv(
    'data/raw/ns_weather-station_2026-07-25.csv',
    header = true,
    all_varchar = true
);
