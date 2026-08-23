-- 00_schema.sql
-- Raw landing table for the committed snapshot, plus the named rules the rest
-- of the pipeline reads. Everything lands as text; typing happens in
-- 02_transform.sql so a bad value fails loudly there instead of turning into a
-- silent NULL here.

CREATE OR REPLACE TABLE raw_closures (
    year       VARCHAR,
    zone       VARCHAR,
    type       VARCHAR,
    site       VARCHAR,
    temporary  VARCHAR,
    scheduled  VARCHAR,
    total      VARCHAR
);

-- Named constants. Every cleaning and measurement rule in this pipeline is
-- either one of these or a macro below, so no rule is buried in an expression.

CREATE OR REPLACE TABLE rule_constants (
    rule_name  VARCHAR,
    rule_value VARCHAR,
    note       VARCHAR
);

INSERT INTO rule_constants VALUES
    ('curly_apostrophe', chr(8217),
     'U+2019. The portal writes site names with a curly apostrophe for 2012-13 through 2018-19 and a straight one from 2019-20 on.'),
    ('ascii_apostrophe', chr(39),
     'U+0027. The canonical apostrophe for site names in this pipeline.'),
    ('fiscal_year_pattern', '^[0-9]{4}-[0-9]{2}$',
     'Every fiscal year label must match this, for example 2023-24. A label that does not match is counted as an excluded row rather than parsed.'),
    ('hours_pattern', '^[0-9]+(\.[0-9]+)?$',
     'Every hours value must match this. A value that does not match is counted as an excluded row rather than cast.'),
    ('share_denominator', 'total',
     'Temporary share is temporary hours divided by the reported total column, guarded so the denominator is greater than zero.');

-- Explicit site rename map. Only genuine renames of the same facility belong
-- here; punctuation differences are handled by canonical_site() below.

CREATE OR REPLACE TABLE rule_site_rename (
    raw_site       VARCHAR,
    canonical_site VARCHAR,
    reason         VARCHAR
);

INSERT INTO rule_site_rename VALUES
    ('Roseway', 'Roseway Hospital',
     'Same facility in Shelburne. The portal uses the short name for 2012-13 through 2018-19 and the full name from 2019-20 on.');

-- Named derivations.

-- The year column holds a fiscal label like 2023-24. The first four characters
-- are the starting calendar year, so 2023-24 gives 2023. Sorting and year
-- arithmetic use this integer, never the label.
CREATE OR REPLACE MACRO fiscal_year_start(label) AS
    CAST(substr(label, 1, 4) AS INTEGER);

-- Site names are trimmed, internal runs of spaces collapsed, and the curly
-- apostrophe folded to the ASCII one. Nothing else about the name changes.
CREATE OR REPLACE MACRO canonical_site(raw) AS
    replace(regexp_replace(trim(raw), '\s+', ' ', 'g'), chr(8217), chr(39));

-- Temporary share of closure hours, in percent, rounded to two decimals for
-- display. NULL when the denominator is zero, which is 238 of the 456
-- site-years in this snapshot.
CREATE OR REPLACE MACRO temporary_share_pct(temp_hours, total_hours) AS
    CASE WHEN total_hours > 0
         THEN CAST(round(100.0 * temp_hours / total_hours, 2) AS DECIMAL(9,2))
    END;

-- Percent change against a previous value, same guard and same rounding.
CREATE OR REPLACE MACRO change_pct(current_value, previous_value) AS
    CASE WHEN previous_value > 0
         THEN CAST(round(100.0 * (current_value - previous_value) / previous_value, 2)
                   AS DECIMAL(9,2))
    END;
