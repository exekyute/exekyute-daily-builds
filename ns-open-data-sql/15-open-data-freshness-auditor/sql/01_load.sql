-- 01_load.sql
-- Question this step answers: what rows are in the pinned snapshot?
-- Read the committed snapshot straight into the raw table. Columns are pinned
-- to VARCHAR so the load never depends on type auto-detection. The path is
-- relative to the project folder, so run.py must be launched from here.

INSERT INTO catalogue_raw
SELECT
  name,
  description,
  detailedmetadata_department,
  type,
  category,
  tags,
  url,
  api_endpoint,
  last_metadata_updated_date,
  last_data_updated_date
FROM read_csv(
  'data/raw/ns_catalogue_2026-07-06.csv',
  header  = true,
  columns = {
    'name':                        'VARCHAR',
    'description':                 'VARCHAR',
    'detailedmetadata_department': 'VARCHAR',
    'type':                        'VARCHAR',
    'category':                    'VARCHAR',
    'tags':                        'VARCHAR',
    'url':                         'VARCHAR',
    'api_endpoint':                'VARCHAR',
    'last_metadata_updated_date':  'VARCHAR',
    'last_data_updated_date':      'VARCHAR'
  }
);
