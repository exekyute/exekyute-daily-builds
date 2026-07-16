-- 00_schema: raw landing table. Every column lands as text so a malformed or
-- empty cell can never fail the load; typing and normalization happen in
-- 02_transform. Columns mirror the committed snapshot header exactly.

CREATE OR REPLACE TABLE trees_raw (
    TREEID    VARCHAR,
    SP_SCIEN  VARCHAR,
    SP_COMM   VARCHAR,
    DBH       VARCHAR,
    INSTYR    VARCHAR,
    OWNER     VARCHAR,
    ASSETSTAT VARCHAR,
    LOCGEN    VARCHAR,
    WIRES     VARCHAR,
    LAT       VARCHAR,
    LON       VARCHAR
);
