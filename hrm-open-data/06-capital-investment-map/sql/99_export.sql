-- 99_export.sql
-- Question this step answers: what are the final, deterministic result files?
-- Write the per-record mart and the three aggregate tables to out/. Every query
-- ends in an ORDER BY so the row order is fixed and the output is byte-for-byte
-- reproducible against expected/. objectid is the unique record key and breaks
-- every ordering tie, though it is not itself a mart column.

COPY (
  SELECT
    proj_no, proj_name, loc_desc, work_desc,
    category, category_norm, asset_type, year, lat, lon
  FROM cap_clean
  ORDER BY category_norm, year, proj_no, loc_desc, objectid
) TO 'out/mart_capital.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT category_norm, year, projects
  FROM counts_by_category_year
  ORDER BY category_norm, year
) TO 'out/counts_by_category_year.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT asset_type, projects
  FROM counts_by_asset_type
  ORDER BY projects DESC, asset_type
) TO 'out/counts_by_asset_type.csv' (HEADER, DELIMITER ',');

COPY (
  SELECT category_rank, category_norm, projects, pct_of_total
  FROM category_ranking
  ORDER BY category_rank, category_norm
) TO 'out/category_ranking.csv' (HEADER, DELIMITER ',');
