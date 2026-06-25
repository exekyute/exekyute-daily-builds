-- Asset register schema for the CCA rollforward.
--
-- Three tables. cca_classes is reference data seeded here. opening_ucc and
-- assets are loaded from CSV by run.py. All money is stored as integer cents so
-- the aggregation stays exact; the runner converts to decimal dollars and applies
-- the CCA rate math with half-up rounding.

CREATE TABLE cca_classes (
    cca_class   TEXT PRIMARY KEY,
    rate        TEXT NOT NULL,   -- declining-balance rate as a decimal string
    description TEXT NOT NULL
);

-- CRA Capital Cost Allowance rates, 2026 tax year. Declining-balance rates from
-- the CRA CCA class list. Review against the CRA class list each year.
INSERT INTO cca_classes (cca_class, rate, description) VALUES
    ('1',    '0.04', 'Most buildings acquired after 1987'),
    ('8',    '0.20', 'Furniture, fixtures, equipment not in another class'),
    ('10',   '0.30', 'General-purpose vehicles and equipment'),
    ('12',   '1.00', 'Tools and small assets written off in full'),
    ('50',   '0.55', 'Computer hardware and systems software'),
    ('53',   '0.50', 'Manufacturing and processing machinery'),
    ('14.1', '0.05', 'Goodwill and other intangibles');

CREATE TABLE opening_ucc (
    cca_class        TEXT NOT NULL,
    opening_ucc_cents INTEGER NOT NULL
);

CREATE TABLE assets (
    asset_id              TEXT NOT NULL,
    description           TEXT NOT NULL,
    cca_class             TEXT NOT NULL,
    capital_cost_cents    INTEGER NOT NULL,
    in_service_date       TEXT NOT NULL,
    disposed              INTEGER NOT NULL,   -- 0 or 1
    disposal_proceeds_cents INTEGER NOT NULL
);
