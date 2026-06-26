-- Schema for the SLA and aging step.
--
-- clean_requests holds the rows written by the intake tool. sla_targets is the
-- resolution target in days for each category, the number of days a request of that
-- category is expected to be closed within.

CREATE TABLE clean_requests (
    request_id   TEXT,
    opened_date  TEXT,
    closed_date  TEXT,
    category     TEXT,
    department   TEXT,
    ward         TEXT,
    status       TEXT
);

CREATE TABLE sla_targets (
    category    TEXT PRIMARY KEY,
    target_days INTEGER
);
