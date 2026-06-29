-- Schema for the model scorecard runner.
-- Two tables, both loaded from CSV by runner.py into an in-memory database.

-- One row per evaluation case run against a model. The gold label is the correct
-- answer, the predicted label is what the model returned. Cost is stored in whole
-- cents so sums stay exact.
CREATE TABLE eval_results (
  eval_id         TEXT,
  model           TEXT,
  task_type       TEXT,
  gold_label      TEXT,
  predicted_label TEXT,
  latency_ms      INTEGER,
  cost_cents      INTEGER
);

-- The per-call LLM costs written by the cost engine (cost_by_call.csv), loaded here
-- so the runner can re-aggregate them and confirm they match the engine to the cent.
CREATE TABLE call_costs (
  record_id  TEXT,
  team       TEXT,
  model      TEXT,
  cost_cents INTEGER
);
