-- 01_load.sql
-- Question this step answers: what rows are in the pinned snapshot?
-- Read the committed snapshot straight into the raw table. The snapshot is the
-- base PPL&C Building Permits attribute set already LEFT JOINed to the geolocated
-- sibling on permit number, so every attribute row is present (18,316) and the
-- 18,224 that geolocated carry a latitude and longitude. Columns are pinned to
-- VARCHAR so the load never depends on type auto-detection. The path is relative
-- to the project folder, so run.py must be launched from here.

INSERT INTO permits_raw
SELECT
  source_object_id, permit_number, date_of_permit_issuance,
  estimated_project_value, work_type, primary_work_scope, permit_status,
  community, district, net_new_units, number_of_storeys, type_of_structure,
  latitude, longitude
FROM read_csv(
  'data/raw/hrm_pplc-building-permits_2026-07-09.csv',
  header  = true,
  columns = {
    'source_object_id':        'VARCHAR',
    'permit_number':           'VARCHAR',
    'date_of_permit_issuance': 'VARCHAR',
    'estimated_project_value': 'VARCHAR',
    'work_type':               'VARCHAR',
    'primary_work_scope':      'VARCHAR',
    'permit_status':           'VARCHAR',
    'community':               'VARCHAR',
    'district':                'VARCHAR',
    'net_new_units':           'VARCHAR',
    'number_of_storeys':       'VARCHAR',
    'type_of_structure':       'VARCHAR',
    'latitude':                'VARCHAR',
    'longitude':               'VARCHAR'
  }
);
