-- 02_transform.sql
-- Clean and type the raw rows:
--   1. trim the text fields
--   2. year_start = the first four digits of the fiscal label ("2025/2026" -> 2025)
--   3. rates cast to DOUBLE; a row where either rate or the year fails to parse is dropped
--   4. one row per (area, area_type, year_start); on duplicates the lowest residential
--      rate wins, then the lowest commercial rate. area alone is NOT unique: six names
--      (Antigonish, Digby, Lunenburg, Pictou, Shelburne, Yarmouth) are both a Town and
--      a Rural Municipality, and those are different municipalities.

CREATE TABLE rates_clean AS
WITH typed AS (
    SELECT
        trim(area)                                        AS area,
        trim(area_type)                                   AS area_type,
        trim(year)                                        AS year_label,
        try_cast(substr(trim(year), 1, 4) AS INTEGER)     AS year_start,
        try_cast(residential AS DOUBLE)                   AS residential_rate,
        try_cast(commercial AS DOUBLE)                    AS commercial_rate
    FROM raw_rates
),
parsed AS (
    SELECT *
    FROM typed
    WHERE year_start IS NOT NULL
      AND residential_rate IS NOT NULL
      AND commercial_rate IS NOT NULL
),
deduped AS (
    SELECT *,
           row_number() OVER (
               PARTITION BY area, area_type, year_start
               ORDER BY residential_rate, commercial_rate
           ) AS rn
    FROM parsed
)
SELECT area, area_type, year_label, year_start, residential_rate, commercial_rate
FROM deduped
WHERE rn = 1;
