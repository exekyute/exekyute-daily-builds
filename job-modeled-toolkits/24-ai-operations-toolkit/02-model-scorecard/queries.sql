-- Analytical queries for the model scorecard. The runner splits this file on the
-- "-- name:" markers and runs each block by name. Counts and percentiles are done
-- here in SQL; the runner turns the counts into precision, recall, F1, cost per
-- correct, and the weighted score with exact decimal arithmetic.

-- name: confusion_matrix
-- Per model, the confusion-matrix counts for the binary triage decision, plus the
-- correct count, the total, and the total eval cost in cents. The positive class is
-- a 'reject' decision (the model flags the item for review).
SELECT
  model,
  SUM(CASE WHEN gold_label = 'reject'  AND predicted_label = 'reject'  THEN 1 ELSE 0 END) AS tp,
  SUM(CASE WHEN gold_label = 'approve' AND predicted_label = 'reject'  THEN 1 ELSE 0 END) AS fp,
  SUM(CASE WHEN gold_label = 'reject'  AND predicted_label = 'approve' THEN 1 ELSE 0 END) AS fn,
  SUM(CASE WHEN gold_label = 'approve' AND predicted_label = 'approve' THEN 1 ELSE 0 END) AS tn,
  SUM(CASE WHEN gold_label = predicted_label THEN 1 ELSE 0 END) AS correct,
  COUNT(*) AS total,
  SUM(cost_cents) AS cost_cents
FROM eval_results
GROUP BY model
ORDER BY model;

-- name: latency_percentiles
-- Per model nearest-rank p50 and p95 latency. The rank is computed with integer
-- ceil so no floating point is involved: ceil(0.50 * n) = (n + 1) / 2 and
-- ceil(0.95 * n) = (95 * n + 99) / 100, both using integer division.
WITH ranked AS (
  SELECT
    model,
    latency_ms,
    ROW_NUMBER() OVER (PARTITION BY model ORDER BY latency_ms, eval_id) AS rn,
    COUNT(*)     OVER (PARTITION BY model) AS n
  FROM eval_results
)
SELECT
  model,
  MAX(CASE WHEN rn = (n + 1) / 2         THEN latency_ms END) AS p50_latency_ms,
  MAX(CASE WHEN rn = (95 * n + 99) / 100 THEN latency_ms END) AS p95_latency_ms
FROM ranked
GROUP BY model
ORDER BY model;

-- name: spend_by_team
-- Re-aggregate the cost engine's per-call costs by team, in cents, to reconcile
-- against the engine's own team totals.
SELECT team, SUM(cost_cents) AS cost_cents
FROM call_costs
GROUP BY team
ORDER BY team;

-- name: spend_total
-- Grand total of the per-call costs in cents. This is the figure that must match
-- the cost engine's direct grand total of $775.85.
SELECT SUM(cost_cents) AS cost_cents
FROM call_costs;
