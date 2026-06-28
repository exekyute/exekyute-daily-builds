-- Schema for the month-end close.
--
-- Four input tables, loaded from the CSVs the upstream tools wrote: the
-- perpetual book inventory, the warehouse physical count, the per-SKU margins,
-- and the excise summary. Money arrives as text in the CSVs and is stored as
-- REAL; every query that totals money wraps the sum in ROUND(..., 2), and the
-- runner re-checks each total with decimal.Decimal so the figures agree with the
-- Python engines to the cent.

CREATE TABLE perpetual (
    sku             TEXT,
    description     TEXT,
    category        TEXT,
    on_hand_qty     REAL,
    unit            TEXT,
    wac_unit_cost   REAL,
    inventory_value REAL,
    integrity_flag  TEXT
);

CREATE TABLE physical_count (
    sku         TEXT,
    counted_qty REAL
);

CREATE TABLE sku_margins (
    fg_sku          TEXT,
    product_line    TEXT,
    channel         TEXT,
    units_sold      REAL,
    unit_price      REAL,
    revenue         REAL,
    cogs_production REAL,
    cogs_excise     REAL,
    cogs_total      REAL,
    gross_margin    REAL,
    margin_pct      REAL
);

CREATE TABLE excise_summary (
    abv_class   TEXT,
    hectolitres REAL,
    excise_duty REAL
);
