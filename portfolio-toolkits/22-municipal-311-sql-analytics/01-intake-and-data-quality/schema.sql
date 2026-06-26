-- Schema for the raw 311 service-request intake.
--
-- One row per reported request, loaded exactly as received before any cleaning.
-- load_seq records the order rows arrived so the data-quality step can keep the
-- first copy of a duplicated request id and flag the later copies.

CREATE TABLE raw_requests (
    load_seq     INTEGER PRIMARY KEY,
    request_id   TEXT,
    opened_date  TEXT,   -- ISO date, YYYY-MM-DD
    closed_date  TEXT,   -- ISO date, or NULL while the request is still open
    category     TEXT,
    department   TEXT,
    ward         TEXT,
    status       TEXT    -- Open or Closed
);
