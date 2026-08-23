-- 00_schema.sql
-- Raw landing table for the committed snapshot, plus the named constants
-- every later file reads. All source columns land as text; typing happens in
-- 02_transform.sql so a bad value fails loudly there, not here.

CREATE OR REPLACE TABLE raw_wait_times (
    period         VARCHAR,
    specialty      VARCHAR,
    procedure      VARCHAR,
    provider       VARCHAR,
    zone           VARCHAR,
    facility       VARCHAR,
    year           VARCHAR,
    quarter        VARCHAR,
    consult_median VARCHAR,
    consult_90th   VARCHAR,
    surgery_median VARCHAR,
    surgery_90th   VARCHAR
);

-- Named constants. Every threshold in this build is declared here and nowhere
-- else; spec.md justifies each one. They are stated assumptions of this build,
-- not official Nova Scotia or pan-Canadian standards.

-- Days. Applies to surgery_median only, never to surgery_90th and never to
-- either consult column. A facility-procedure-quarter line breaches when its
-- published surgery_median exceeds this number.
CREATE OR REPLACE MACRO surgery_target_days() AS 182;

-- Days. A separate target, applied only to consult_median. Consultation and
-- surgery are different queues, so they never share a threshold.
CREATE OR REPLACE MACRO consult_target_days() AS 90;

-- Rows. A facility or procedure with fewer measured lines than this gets a
-- meets_min_rows flag of 0 in the ranked sections. Nothing is dropped for
-- being thin; the flag exists so a 25 percent rate on eight lines is not read
-- as if it carried the same weight as one on seven hundred.
CREATE OR REPLACE MACRO min_measured_rows() AS 9;

-- Rows. How many facility-procedure-quarter lines the worst_lines section
-- carries. A display cut only; it changes no computed figure.
CREATE OR REPLACE MACRO worst_lines_shown() AS 25;
