-- 99_export.sql
-- Question this step answers: what are the final, deterministic result files?
-- Write the two marts and the coverage summary to out/. Every query ends in an
-- ORDER BY so the row order is fixed and the output is byte-for-byte
-- reproducible against expected/. busstopid is unique per stop and PNR_NAME is
-- unique per lot (15 distinct), so each ordering is total; the coordinate
-- tie-breakers on the park and ride export are belt and braces.

COPY (
  SELECT busstopid, stopnumber, location, accessible, status, has_shelter, lat, lon
  FROM mart_stops
  ORDER BY busstopid
) TO 'out/mart_stops.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT name, capacity, routes, lat, lon
  FROM mart_parkride
  ORDER BY name, lat, lon
) TO 'out/mart_parkride.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT total_stops, accessible_stops, accessible_share_pct, total_shelters,
         stops_with_shelter, shelter_coverage_pct, parkride_lots, parkride_capacity
  FROM access_summary
  ORDER BY total_stops
) TO 'out/access_summary.csv' (HEADER, DELIMITER ',');
