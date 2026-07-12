-- 99_export.sql
-- Question this step answers: how do we write the final Pareto out for verification?
-- Copies the result table to out/vendor_pareto.csv, ordered so the file is byte-stable
-- from one run to the next. The path is relative; run.py runs from this folder.

COPY (
  SELECT *
  FROM vendor_pareto
  ORDER BY vendor_rank
) TO 'out/vendor_pareto.csv' (HEADER, DELIMITER ',');
