-- 00_schema.sql
-- Raw landing table for the committed snapshot. All columns land as text;
-- typing happens in 02_transform.sql so bad values fail loudly there, not here.

CREATE OR REPLACE TABLE raw_payments (
    department     VARCHAR,
    division       VARCHAR,
    program_name   VARCHAR,
    client_name    VARCHAR,
    payment_amount VARCHAR,
    fiscal_year    VARCHAR
);
