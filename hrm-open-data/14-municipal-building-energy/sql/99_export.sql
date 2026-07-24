-- 99_export.sql
-- Question this step answers: what are the final, deterministic result files and
-- the frozen BI mart?
-- Write the three golden results to out/ and the single frozen mart to
-- bi/exports/. Every query ends in an ORDER BY so the row order is stable and the
-- output is byte-for-byte reproducible against expected/. The mart is the exact
-- table Tableau and Power BI import, so both tools read the same frozen cents the
-- golden totals verify.

-- Golden 1: total cost by fuel, costliest fuel first.
COPY (
  SELECT *
  FROM cost_by_fuel
  ORDER BY cost DESC, energy_type
) TO 'out/cost_by_fuel.csv' (HEADER, DELIMITER ',');

-- Golden 2: the costliest buildings by total cost, costliest first.
COPY (
  SELECT *
  FROM costliest_buildings
  ORDER BY cost DESC, building_name
) TO 'out/costliest_buildings.csv' (HEADER, DELIMITER ',');

-- Golden 3: cost per unit by fuel, ordered by fuel name (units differ, so no
-- cross-fuel magnitude ordering is implied).
COPY (
  SELECT *
  FROM cost_per_unit_by_fuel
  ORDER BY energy_type
) TO 'out/cost_per_unit_by_fuel.csv' (HEADER, DELIMITER ',');

-- Frozen mart for both BI tools: one row per building and energy type.
COPY (
  SELECT *
  FROM mart_energy
  ORDER BY building_name, energy_type
) TO 'bi/exports/mart_energy.csv' (HEADER, DELIMITER ',');
