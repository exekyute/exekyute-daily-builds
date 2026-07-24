-- 03_analysis.sql
-- The analytical core. One frozen mart for the BI faces, three golden result
-- tables, and a headline. Every dollar is already rounded to the cent in
-- 02_transform, so each SUM below is a sum of clean cents and the fuel totals and
-- the building totals both tie to the same grand total exactly. Consumption is
-- summed only within a single fuel and its unit, never across fuels, because the
-- four fuels are metered in three different units. Only cost is summed across
-- fuels. cost_per_unit is guarded against a non-positive consumption base (the two
-- building-and-fuel groups whose net consumption goes negative once meter
-- adjustments are applied), rendering NULL there rather than a meaningless figure.

-- Mart (the one frozen face): one row per building and energy type, 285 rows.
-- Powers both the Tableau extract and the Power BI import. consumption is the
-- within-fuel sum in that fuel's unit; cost is the summed cents; cost_per_unit is
-- cost over consumption, in dollars per unit, to four decimals, NULL when the base
-- is not positive.
CREATE TABLE mart_energy AS
SELECT
  building_name,
  hrm_building_id,
  energy_type,
  unit_of_measure,
  SUM(consumption) AS consumption,
  SUM(cost)        AS cost,
  CASE
    WHEN SUM(consumption) > 0
    THEN CAST(round(CAST(SUM(cost) AS DOUBLE) / CAST(SUM(consumption) AS DOUBLE), 4) AS DECIMAL(18, 4))
  END AS cost_per_unit
FROM energy_clean
GROUP BY building_name, hrm_building_id, energy_type, unit_of_measure;

-- Golden 1: total cost by fuel, 4 rows. Reads which fuel drives municipal energy
-- cost. meter_readings and building_count come from the reading-level and the
-- mart grains; cost_share is each fuel's share of the municipal energy cost; the
-- consumption is the within-fuel total in that fuel's own unit. Ranked by cost.
CREATE TABLE cost_by_fuel AS
WITH reads AS (
  SELECT energy_type, COUNT(*) AS meter_readings
  FROM energy_clean
  GROUP BY energy_type
),
fuel AS (
  SELECT
    energy_type,
    MIN(unit_of_measure)  AS unit_of_measure,
    COUNT(*)              AS building_count,
    SUM(consumption)      AS consumption,
    SUM(cost)             AS cost
  FROM mart_energy
  GROUP BY energy_type
)
SELECT
  f.energy_type,
  f.unit_of_measure,
  r.meter_readings,
  f.building_count,
  f.consumption,
  f.cost,
  CAST(round(CAST(f.cost AS DOUBLE) / SUM(f.cost) OVER (), 6) AS DECIMAL(18, 6)) AS cost_share,
  DENSE_RANK() OVER (ORDER BY f.cost DESC)                                       AS fuel_rank
FROM fuel f
JOIN reads r USING (energy_type);

-- Golden 2: the costliest buildings by total cost, 160 rows. Cost is summable
-- across fuels, so this rolls the mart to the building and sums every fuel's cost.
-- There is deliberately no consumption column here: consumption cannot be summed
-- across fuels. fuel_count is how many of the four fuels the building uses;
-- cost_share is the building's share of the municipal energy cost. Ranked by cost.
CREATE TABLE costliest_buildings AS
WITH b AS (
  SELECT
    building_name,
    hrm_building_id,
    COUNT(*)   AS fuel_count,
    SUM(cost)  AS cost
  FROM mart_energy
  GROUP BY building_name, hrm_building_id
)
SELECT
  building_name,
  hrm_building_id,
  fuel_count,
  cost,
  CAST(round(CAST(cost AS DOUBLE) / SUM(cost) OVER (), 6) AS DECIMAL(18, 6)) AS cost_share,
  DENSE_RANK() OVER (ORDER BY cost DESC)                                     AS building_rank
FROM b;

-- Golden 3: cost per unit by fuel, 4 rows. The unit economics view. Because the
-- units differ (GJ, kWh, L), the per-unit figures are not comparable across rows;
-- each is the blended dollars-per-unit within its own fuel. Aggregating the cost
-- and the consumption before dividing (rather than averaging the mart's row-level
-- cost_per_unit) is the correct way to blend a ratio. Ordered by fuel name so no
-- ordering implies a cross-unit comparison.
CREATE TABLE cost_per_unit_by_fuel AS
SELECT
  energy_type,
  MIN(unit_of_measure) AS unit_of_measure,
  SUM(consumption)     AS consumption,
  SUM(cost)            AS cost,
  CASE
    WHEN SUM(consumption) > 0
    THEN CAST(round(CAST(SUM(cost) AS DOUBLE) / CAST(SUM(consumption) AS DOUBLE), 4) AS DECIMAL(18, 4))
  END AS cost_per_unit
FROM mart_energy
GROUP BY energy_type;

-- Headline: the total municipal energy cost across the record and the single
-- costliest building, as two ready-to-read lines for the console. run.py prints
-- these; it computes nothing.
CREATE TABLE headline AS
SELECT
  1 AS ord,
  'Total municipal energy cost across the record: $'
    || format('{:,.2f}', CAST((SELECT SUM(cost) FROM mart_energy) AS DOUBLE))
    || ' across ' || (SELECT COUNT(*) FROM cost_by_fuel) || ' fuels and '
    || (SELECT COUNT(*) FROM costliest_buildings) || ' buildings.' AS line
UNION ALL
SELECT
  2 AS ord,
  'Costliest building: ' || building_name || ' (' || hrm_building_id || '), $'
    || format('{:,.2f}', CAST(cost AS DOUBLE)) || ' ('
    || format('{:.1f}', CAST(100.0 * cost_share AS DOUBLE))
    || '% of the municipal energy cost).' AS line
FROM costliest_buildings
WHERE building_rank = 1
ORDER BY ord;
