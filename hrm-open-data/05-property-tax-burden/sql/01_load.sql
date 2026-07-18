-- 01_load.sql
-- Question this step answers: what rows are in the pinned snapshot?
-- Read the committed grouped snapshot straight into the raw table. Columns are
-- pinned to VARCHAR so the load never depends on type auto-detection. The path is
-- relative to the project folder, so run.py must be launched from here.

INSERT INTO tax_raw
SELECT tax_group, tax_summary_group, rate_code, rate_description,
       bill_rate_percentage, account_count, residential_taxable,
       commercial_taxable, resource_taxable, bill_value, bill_amount
FROM read_csv(
  'data/raw/hrm_tax-bill-info_2026-07-09.csv',
  header  = true,
  columns = {
    'tax_group':            'VARCHAR',
    'tax_summary_group':    'VARCHAR',
    'rate_code':            'VARCHAR',
    'rate_description':      'VARCHAR',
    'bill_rate_percentage': 'VARCHAR',
    'account_count':        'VARCHAR',
    'residential_taxable':  'VARCHAR',
    'commercial_taxable':   'VARCHAR',
    'resource_taxable':     'VARCHAR',
    'bill_value':           'VARCHAR',
    'bill_amount':          'VARCHAR'
  }
);
