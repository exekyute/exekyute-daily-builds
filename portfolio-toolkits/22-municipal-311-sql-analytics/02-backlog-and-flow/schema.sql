-- Schema for the backlog and flow step.
--
-- clean_requests holds the rows written by the intake tool. category_cost_rates is
-- the standard cost to serve one request of each category, in whole cents so the
-- money stays exact. periods is the list of reporting months, seeded by the runner
-- from the open dates in the data, with half-open [start_date, next_date) bounds.

CREATE TABLE clean_requests (
    request_id   TEXT,
    opened_date  TEXT,
    closed_date  TEXT,
    category     TEXT,
    department   TEXT,
    ward         TEXT,
    status       TEXT
);

CREATE TABLE category_cost_rates (
    category   TEXT PRIMARY KEY,
    cost_cents INTEGER
);

CREATE TABLE periods (
    period     TEXT PRIMARY KEY,  -- YYYY-MM
    start_date TEXT,              -- inclusive
    next_date  TEXT               -- exclusive
);
