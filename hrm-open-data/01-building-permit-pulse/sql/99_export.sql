-- 99_export.sql
-- Question this step answers: what are the final, deterministic result files?
-- Write the two goldens, the community dashboard feed, and the frozen per-permit
-- mart the BI tools and the browser dashboard all read. Every query ends in an
-- ORDER BY so each file is byte-for-byte reproducible against expected/.

-- Golden A: activity and value by issue year and work type.
COPY (
  SELECT issue_year, work_type, permit_count, total_project_value, total_net_new_units
  FROM permits_by_year_worktype
  ORDER BY issue_year, work_type
) TO 'out/permits_by_year_worktype.csv' (HEADER, DELIMITER ',');

-- Golden B: per-district running total of net new units by year.
COPY (
  SELECT district, issue_year, net_new_units, cumulative_net_new_units
  FROM district_units_running_total
  ORDER BY district, issue_year
) TO 'out/district_units_running_total.csv' (HEADER, DELIMITER ',');

-- Dashboard feed: value and units by community, ranked by declared value.
COPY (
  SELECT community, permit_count, total_project_value, total_net_new_units
  FROM permits_by_community
  ORDER BY total_project_value DESC, community
) TO 'out/permits_by_community.csv' (HEADER, DELIMITER ',');

-- Frozen mart: one row per permit for Tableau, Power BI, and the dashboard. The
-- ORDER BY source_object_id fixes the row order across all three faces. Only the
-- thirteen dashboard columns are projected; source_object_id orders but is not
-- emitted.
COPY (
  SELECT
    permit_number, issue_year, issue_month, community, district, work_type,
    primary_work_scope, project_value, net_new_units, storeys, permit_status, lat, lon
  FROM permit_mart
  ORDER BY source_object_id
) TO 'out/mart_permits.csv' (HEADER, DELIMITER ',');
