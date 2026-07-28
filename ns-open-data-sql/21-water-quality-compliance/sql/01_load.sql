-- 01_load.sql
-- Load the pinned snapshot. The filename carries the pull date, and that
-- date is repeated as the PULL_DATE constant in 00_schema.sql. Swapping in
-- a newer snapshot means changing both and re-baselining
-- expected/water_compliance.csv on purpose.

INSERT INTO raw_results
SELECT
    datasetname,
    monitoringlocationid,
    monitoringlocationname,
    monitoringlocationtype,
    activitytype,
    activitymedianame,
    activitystartdate,
    activitystarttime,
    activitydepthheightmeasure,
    activitydepthheightunit,
    samplecollectionequipmentname,
    characteristicname,
    methodspeciation,
    resultsamplefraction,
    resultvalue,
    resultunit,
    resultvaluetype,
    resultdetectioncondition,
    resultdetectionquantitationlimitmeasure,
    resultdetectionquantitationlimitunit,
    resultdetectionquantitationlimittype,
    resultstatusid,
    resultcomment,
    laboratoryname,
    laboratorysampleid,
    monitoringlocationwaterbody
FROM read_csv(
    'data/raw/ns_surface-water-grab_2026-07-25.csv',
    header = true,
    all_varchar = true
);
