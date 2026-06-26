-- Schema for the membership reporting database.
-- Two tables: the membership tiers (a small reference table) and the members.
-- The runner creates these tables, seeds the tiers below, and loads the
-- members from sample_members.csv.

CREATE TABLE tiers (
    tier        TEXT PRIMARY KEY,   -- Student, Associate, Professional, Retired
    annual_dues REAL NOT NULL       -- full-year dues for the tier, in dollars
);

INSERT INTO tiers (tier, annual_dues) VALUES
    ('Student',      75.00),
    ('Associate',   150.00),
    ('Professional', 300.00),
    ('Retired',      90.00);

CREATE TABLE members (
    member_id   INTEGER,        -- not unique on purpose: duplicates are a data error to catch
    name        TEXT,
    tier        TEXT,           -- may be blank when a record is incomplete
    join_month  INTEGER,        -- month the member joined (1-12), used for proration
    status      TEXT,           -- Paid, Expiring, Lapsed, or Duplicate
    dues        REAL,           -- prorated dues already billed, in dollars (blank if incomplete)
    late_fee    REAL,           -- 25.00 when renewed after the grace period, else 0.00
    expiry_date TEXT            -- ISO date the membership expires
);
