-- 00_schema.sql
-- Two things live here: the raw landing table for the committed snapshot,
-- and every named constant the pipeline compares against. Nothing in
-- 02 or 03 is allowed to carry a bare threshold, unit string, or accepted
-- value; it all comes from the const_ tables below so a reader can audit
-- the rules in one place. spec.md justifies each one and cites its source.

-- Raw landing table. All 26 published columns land as text; typing happens
-- in 02_transform.sql so a bad value is classified and counted there rather
-- than turning into a silent NULL here.
CREATE OR REPLACE TABLE raw_results (
    datasetname                             VARCHAR,
    monitoringlocationid                    VARCHAR,
    monitoringlocationname                  VARCHAR,
    monitoringlocationtype                  VARCHAR,
    activitytype                            VARCHAR,
    activitymedianame                       VARCHAR,
    activitystartdate                       VARCHAR,
    activitystarttime                       VARCHAR,
    activitydepthheightmeasure              VARCHAR,
    activitydepthheightunit                 VARCHAR,
    samplecollectionequipmentname           VARCHAR,
    characteristicname                      VARCHAR,
    methodspeciation                        VARCHAR,
    resultsamplefraction                    VARCHAR,
    resultvalue                             VARCHAR,
    resultunit                              VARCHAR,
    resultvaluetype                         VARCHAR,
    resultdetectioncondition                VARCHAR,
    resultdetectionquantitationlimitmeasure VARCHAR,
    resultdetectionquantitationlimitunit    VARCHAR,
    resultdetectionquantitationlimittype    VARCHAR,
    resultstatusid                          VARCHAR,
    resultcomment                           VARCHAR,
    laboratoryname                          VARCHAR,
    laboratorysampleid                      VARCHAR,
    monitoringlocationwaterbody             VARCHAR
);

-- PULL_DATE. The date the snapshot was taken. Every elapsed-time figure in
-- the pipeline is measured against this literal and never against
-- CURRENT_DATE, so re-running the build next month does not move a single
-- number in the golden file.
CREATE OR REPLACE TABLE const_run AS
SELECT DATE '2026-07-25' AS pull_date;

-- ACCEPTED_ACTIVITY_TYPE. A positive allowlist of WQX activity types that
-- represent a real environmental measurement. Both values present in this
-- snapshot are real measurements: 'Sample-Routine' is the grab sample sent
-- to the lab, 'Field Msr/Obs-Portable Data Logger' is the calibrated sonde
-- reading taken at the same visit. Everything else is refused, which is
-- what keeps WQX quality-control types out: 'Quality Control Sample-Field
-- Blank' and 'Quality Control Sample-Trip Blank' read near zero and would
-- drag a pass rate up, 'Quality Control Sample-Field Replicate' and
-- 'Quality Control Sample-Lab Duplicate' repeat one sample and would count
-- it twice. This snapshot contains none of those four, so the filter
-- removes 0 rows today; it stays an allowlist so a later pull that does
-- carry them is handled without editing the SQL.
CREATE OR REPLACE TABLE const_accepted_activitytype (activitytype VARCHAR);
INSERT INTO const_accepted_activitytype VALUES
    ('Sample-Routine'),
    ('Field Msr/Obs-Portable Data Logger');

-- ACCEPTED_RESULT_STATUS. The network publishes every result it has
-- validated for release under the single status 'Preliminary', so that is
-- the whole allowlist. A row whose status is blank or carries any other
-- value has not been released under a status this pipeline recognises and
-- is excluded and counted, not guessed at.
CREATE OR REPLACE TABLE const_accepted_resultstatus (resultstatusid VARCHAR);
INSERT INTO const_accepted_resultstatus VALUES
    ('Preliminary');

-- UNIT_CONVERSION. The reason this table exists: the same analyte is
-- published in more than one unit, and a milligram-per-litre threshold
-- compared against a microgram-per-litre reading is wrong by a factor of
-- 1000 while still producing a tidy number that passes a golden diff. No
-- comparison in 02 or 03 happens until the row's unit has been converted
-- into the unit its guideline is written in, using a factor from this
-- table. A row whose unit has no entry here is excluded as wrong_unit and
-- counted; it is never compared and never silently dropped.
CREATE OR REPLACE TABLE const_unit_conversion (
    from_unit VARCHAR,
    to_unit   VARCHAR,
    factor    DECIMAL(18,6)
);
INSERT INTO const_unit_conversion VALUES
    ('mg/l', 'mg/l', 1),
    ('ug/l', 'ug/l', 1),
    ('ug/l', 'mg/l', 0.001),
    ('mg/l', 'ug/l', 1000);

-- ANALYTE_GUIDELINE. One row per (analyte, sample fraction) pair in scope,
-- carrying the unit the guideline is written in, the numeric threshold, and
-- the direction of the test. Every threshold is a CCME Canadian Water
-- Quality Guideline for the Protection of Aquatic Life, freshwater; the
-- guideline_source column carries the citation and spec.md repeats it in
-- full. Only guidelines that are a single fixed number are listed: the
-- hardness-dependent metals (cadmium, copper, lead, nickel, zinc), the
-- pH-dependent aluminium guideline, the temperature-and-pH-dependent
-- ammonia guideline, and the change-from-background guidelines (turbidity,
-- suspended solids) need per-sample covariates this dataset does not carry
-- on the same row, so applying a single number to them would be wrong.
--
-- sample_fraction is part of the key on purpose. The metals guidelines are
-- written for the total fraction, and this dataset also publishes a
-- dissolved fraction for the same analyte on the same visit. Counting both
-- would measure one sample twice against a guideline that only applies to
-- one of them, so the dissolved rows are excluded and counted.
--
-- Boron is declared in mg/L, the unit CCME publishes it in, while the
-- dataset reports boron in ug/L. That is where the unit conversion above
-- earns its place: compared raw against 1.5, nearly every boron reading
-- in this snapshot would register as a breach.
CREATE OR REPLACE TABLE const_analyte_guideline (
    analyte          VARCHAR,
    sample_fraction  VARCHAR,
    guideline_unit   VARCHAR,
    threshold        DECIMAL(12,3),
    direction        VARCHAR,
    guideline_source VARCHAR
);
INSERT INTO const_analyte_guideline VALUES
    ('Arsenic',               'Total',        'ug/l',   5.0,   'maximum',
     'CCME CWQG for the protection of aquatic life, freshwater, long-term: 5.0 ug/L'),
    ('Boron',                 'Total',        'mg/l',   1.5,   'maximum',
     'CCME CWQG for the protection of aquatic life, freshwater, long-term: 1.5 mg/L'),
    ('Chloride',              'Dissolved',    'mg/l',   120.0, 'maximum',
     'CCME CWQG for the protection of aquatic life, freshwater, long-term: 120 mg/L'),
    ('Dissolved oxygen (DO)', '(not stated)', 'mg/l',   6.5,   'minimum',
     'CCME CWQG for the protection of aquatic life, freshwater, cold-water biota, other than early life stages: 6.5 mg/L'),
    ('Iron',                  'Total',        'ug/l',   300.0, 'maximum',
     'CCME CWQG for the protection of aquatic life, freshwater: 300 ug/L'),
    ('Molybdenum',            'Total',        'ug/l',   73.0,  'maximum',
     'CCME CWQG for the protection of aquatic life, freshwater, long-term: 73 ug/L'),
    ('Selenium',              'Total',        'ug/l',   1.0,   'maximum',
     'CCME CWQG for the protection of aquatic life, freshwater, long-term: 1 ug/L'),
    ('Silver',                'Total',        'ug/l',   0.25,  'maximum',
     'CCME CWQG for the protection of aquatic life, freshwater, interim: 0.25 ug/L'),
    ('Thallium',              'Total',        'ug/l',   0.8,   'maximum',
     'CCME CWQG for the protection of aquatic life, freshwater, interim: 0.8 ug/L'),
    ('Uranium',               'Total',        'ug/l',   15.0,  'maximum',
     'CCME CWQG for the protection of aquatic life, freshwater, long-term: 15 ug/L');
