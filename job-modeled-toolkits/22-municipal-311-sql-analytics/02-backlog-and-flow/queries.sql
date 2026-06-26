-- Backlog and flow queries.
--
-- The flow identity for any department and month is:
--   opening + new - closed = closing
-- opening counts requests still open at the start of the month, new counts requests
-- opened during the month, closed counts requests closed during the month, and
-- closing counts requests still open at the end of the month. closing is counted
-- independently here, so the runner can confirm the identity holds rather than
-- assume it.

-- name: period_summary
-- For each department and month: the opening backlog, requests opened, requests
-- closed, the independently counted closing backlog, and the cost to serve the
-- requests closed that month.
WITH depts AS (
    SELECT DISTINCT department FROM clean_requests
),
grid AS (
    SELECT p.period, p.start_date, p.next_date, d.department
    FROM periods p
    CROSS JOIN depts d
)
SELECT
    g.period,
    g.department,
    (SELECT COUNT(*) FROM clean_requests c
        WHERE c.department = g.department
          AND c.opened_date < g.start_date
          AND (c.closed_date IS NULL OR c.closed_date >= g.start_date)
    ) AS opening,
    (SELECT COUNT(*) FROM clean_requests c
        WHERE c.department = g.department
          AND c.opened_date >= g.start_date
          AND c.opened_date < g.next_date
    ) AS new_requests,
    (SELECT COUNT(*) FROM clean_requests c
        WHERE c.department = g.department
          AND c.closed_date IS NOT NULL
          AND c.closed_date >= g.start_date
          AND c.closed_date < g.next_date
    ) AS closed,
    (SELECT COUNT(*) FROM clean_requests c
        WHERE c.department = g.department
          AND c.opened_date < g.next_date
          AND (c.closed_date IS NULL OR c.closed_date >= g.next_date)
    ) AS closing,
    (SELECT COALESCE(SUM(r.cost_cents), 0) FROM clean_requests c
        JOIN category_cost_rates r ON r.category = c.category
        WHERE c.department = g.department
          AND c.closed_date IS NOT NULL
          AND c.closed_date >= g.start_date
          AND c.closed_date < g.next_date
    ) AS cost_to_serve_cents
FROM grid g
ORDER BY g.period, g.department;
