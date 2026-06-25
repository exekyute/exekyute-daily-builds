-- Saved reports the coordinator runs a few times a week.
-- Each report is marked with "-- name: <id>" so the Python runner can find and
-- run it. The reports stay deliberately simple: SELECT, WHERE, one JOIN,
-- GROUP BY, ORDER BY, COUNT, SUM, and a single CASE.
--
-- A note on tax: GST/HST (13%) applies to dues. The late renewal fee is not
-- taxed. The dues summary applies the 13% to the summed dues for each tier, not
-- to each member one at a time, so the cents do not drift. The runner does that
-- rounding with Decimal and prints the tax and totals next to these results.


-- name: expiring_worklist
-- Members due to expire in the next 30 days. The CASE adds a plain action label.
SELECT
    member_id,
    name,
    tier,
    status,
    expiry_date,
    CASE
        WHEN status = 'Expiring' THEN 'Renew now'
        WHEN status = 'Lapsed'   THEN 'Overdue'
        ELSE 'Current'
    END AS action
FROM members
WHERE status = 'Expiring'
ORDER BY expiry_date;


-- name: lapsed_worklist
-- Members who lapsed in the past 30 days, oldest expiry first.
SELECT
    member_id,
    name,
    tier,
    status,
    expiry_date
FROM members
WHERE status = 'Lapsed'
ORDER BY expiry_date;


-- name: dues_summary_by_tier
-- The monthly dues summary the manager reviews: how many members and how much
-- in dues per tier. Duplicate and incomplete records are left out.
SELECT
    tier,
    COUNT(*)   AS members,
    SUM(dues)  AS dues
FROM members
WHERE status IN ('Paid', 'Expiring', 'Lapsed')
  AND dues IS NOT NULL
GROUP BY tier
ORDER BY tier;


-- name: dues_summary_total
-- The same billable set as one grand line: member count, total dues, total
-- late fees. The runner adds HST and the grand total.
SELECT
    COUNT(*)      AS members,
    SUM(dues)     AS dues,
    SUM(late_fee) AS late_fees
FROM members
WHERE status IN ('Paid', 'Expiring', 'Lapsed')
  AND dues IS NOT NULL;


-- name: proration_check
-- Joins each member to the tier table to show full-year dues next to the dues
-- actually billed, so a part-year (prorated) membership is easy to spot.
SELECT
    m.member_id,
    m.name,
    m.tier,
    t.annual_dues,
    m.dues AS billed_dues,
    m.join_month
FROM members m
JOIN tiers t ON m.tier = t.tier
WHERE m.status IN ('Paid', 'Expiring', 'Lapsed')
ORDER BY m.member_id;


-- name: reconciliation
-- Counts used to reconcile the database against the Excel worklist: total rows,
-- distinct members, and how many are billable. The gap flags duplicate or
-- incomplete records.
SELECT
    COUNT(*)                  AS total_rows,
    COUNT(DISTINCT member_id) AS distinct_members,
    SUM(CASE WHEN status IN ('Paid', 'Expiring', 'Lapsed') AND dues IS NOT NULL
             THEN 1 ELSE 0 END) AS billable_members
FROM members;


-- name: worklist_all
-- Every member with the action label, used to build the renewal worklist CSV
-- that the Excel and dashboard tools read. The runner adds HST and total.
SELECT
    member_id,
    name,
    tier,
    status,
    expiry_date,
    dues,
    late_fee,
    CASE
        WHEN status = 'Expiring' THEN 'Renew now'
        WHEN status = 'Lapsed'   THEN 'Overdue'
        WHEN status = 'Duplicate' THEN 'Review'
        ELSE 'Current'
    END AS action
FROM members
ORDER BY member_id;
