-- 02_transform.sql
-- Question this step answers: what does one clean, typed reading row look like?
-- Trim the text fields, cast consumption to a fixed three-decimal number (the
-- source carries at most three decimals), and round the dollar cost to the cent
-- once. Rounding money here, one time, means every later total is a sum of clean
-- cents and ties exactly with no floating-point drift. Negative and zero readings
-- are meter adjustments, credits, and corrections; they are real accounting
-- entries, so they are kept and summed, not filtered. This step does not change
-- the grain: it is still one row per reading, just cleaned and typed.

CREATE TABLE energy_clean AS
SELECT
  trim(energy_type)                             AS energy_type,
  trim(building_name)                           AS building_name,
  trim(hrm_building_id)                         AS hrm_building_id,
  trim(unit_of_measure)                         AS unit_of_measure,
  CAST(round(CAST(consumption AS DOUBLE), 3) AS DECIMAL(18, 3)) AS consumption,
  CAST(round(CAST(cost        AS DOUBLE), 2) AS DECIMAL(18, 2)) AS cost
FROM energy_raw
WHERE energy_type IS NOT NULL AND trim(energy_type) <> ''
  AND building_name IS NOT NULL AND trim(building_name) <> '';
