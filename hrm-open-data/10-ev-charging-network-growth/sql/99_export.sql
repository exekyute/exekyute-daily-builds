-- 99_export.sql
-- Question this step answers: what are the final, deterministic result files?
-- Write the per-charger mart and the three aggregate tables to out/. Every query
-- ends in an ORDER BY so the row order is fixed and the output is byte-for-byte
-- reproducible against expected/. evcsid is the unique station key and breaks
-- every ordering tie.

COPY (
  SELECT
    evcsid, owner, chartype, connectype, power_kw, location, access,
    install_year, quantity, lat, lon
  FROM ev_clean
  ORDER BY install_year, chartype, connectype, evcsid
) TO 'out/mart_ev.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT install_year, chargers, cumulative_chargers
  FROM chargers_by_year
  ORDER BY install_year
) TO 'out/chargers_by_year.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT chartype, chargers
  FROM counts_by_chartype
  ORDER BY chargers DESC, chartype
) TO 'out/counts_by_chartype.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT connectype, chargers
  FROM counts_by_connectype
  ORDER BY chargers DESC, connectype
) TO 'out/counts_by_connectype.csv' (HEADER, DELIMITER ',');
