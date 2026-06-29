# Model scorecard

## Purpose
Scores and ranks the models a team could use for one task, from a set of evaluation
results, and reconciles the team's spend against the cost engine. An AI operations
analyst runs it to decide which model to use, balancing quality, latency, and cost,
and to confirm the chargeback numbers tie out.

## Inputs
Two CSV files, read from this folder.

`eval_results.csv`, one row per evaluation case run against a model:
- `eval_id` (text, unique)
- `model` (text)
- `task_type` (text)
- `gold_label` (`approve` or `reject`, the correct answer)
- `predicted_label` (`approve` or `reject`, what the model returned)
- `latency_ms` (whole number, greater than zero)
- `cost_usd` (dollar amount, the cost of that eval call)

`cost_by_call.csv`, the per-call output of the cost engine (tool 01). The runner reads
its `record_id`, `team`, `model`, and `cost` columns to reconcile spend.

The decision being evaluated is binary. The positive class is a `reject` (the model
flags the item for review), so precision and recall are measured against `reject`.

## Validation rules
- A missing column in either file stops the run.
- `eval_id` is required and must be unique. A repeat stops the run.
- `gold_label` and `predicted_label` must each be `approve` or `reject`.
- `latency_ms` must be a whole number greater than zero.
- `cost_usd` must be a number.

## Logic
The queries in `queries.sql` do the aggregation; the runner turns the counts into the
reported metrics with exact decimal arithmetic.

1. `confusion_matrix` counts, per model, the true and false positives and negatives,
   the correct count, the total, and the total eval cost in cents.
2. The runner computes accuracy (correct / total), precision (tp / (tp + fp)), recall
   (tp / (tp + fn)), and F1 (2 tp / (2 tp + fp + fn)), each rounded half up to four places.
3. `latency_percentiles` computes the nearest-rank p50 and p95 latency per model. The
   rank uses integer ceil so no floating point is involved: the p50 rank is
   (n + 1) / 2 and the p95 rank is (95 n + 99) / 100, both integer division.
4. Cost per correct is the total eval cost divided by the correct count.
5. The weighted score combines three parts: quality at 0.5, cost at 0.3, and speed at
   0.2. Quality is the F1 score. Cost and speed are scaled across the models on the
   card, so the cheapest cost-per-correct and the lowest p95 latency each score one
   and the highest each score zero. The score is `100 x (0.5 F1 + 0.3 cost + 0.2 speed)`,
   rounded to two places. Models are ranked by score, best first.
6. `spend_total` and `spend_by_team` re-aggregate the cost engine's per-call costs in
   cents. The runner confirms the grand total and every team total match the engine.

## Outputs
- Printed to the console: the ranked scorecard, the spend reconciliation, and a PASS
  or FAIL line from the checks.
- `model_scorecard.csv`: rank, model, accuracy, precision, recall, F1, p50 and p95
  latency, total cost, cost per correct, and score. This is the file the dashboard reads.

## Edge cases
The sample data exercises each branch in one run:
- A high-quality model with one false positive (frontier-large, accuracy 0.9000,
  recall 1.0000).
- A balanced model that misses one each way (balanced-mid, precision and recall 0.8000).
- A weaker, cheaper, faster model (frontier-mini, every metric 0.6000).
- A latency outlier in each model's tail that becomes its p95.
- A scoring outcome where the cheapest and fastest model ranks first even though it
  has the lowest accuracy, which is the tradeoff the weights are there to make visible.
- The reconciliation against the cost engine, which must match to the cent.
- `eval_results_bad.csv` carries a row whose predicted label is neither `approve` nor
  `reject`, so the runner rejects the file with a clear message.

### Hand-checked example
Running against the sample files:

- frontier-large: tp 5, fp 1, fn 0, so precision 5/6 = 0.8333, recall 5/5 = 1.0000,
  F1 10/11 = 0.9091, accuracy 9/10 = 0.9000. p50 1100 ms, p95 2000 ms. Eval cost
  $1.00 over 9 correct is $0.1111 per correct. Score 45.45.
- balanced-mid: tp 4, fp 1, fn 1, so precision, recall, and F1 are all 0.8000,
  accuracy 0.8000. p50 500 ms, p95 900 ms. $0.0500 per correct. Score 74.08.
- frontier-mini: tp 3, fp 2, fn 2, so every quality metric is 0.6000. p50 250 ms,
  p95 500 ms. $0.0167 per correct. Score 80.00, which ranks it first.
- Spend reconciliation: the per-call costs sum to 77,585 cents, or **$775.85**, the
  same grand total the cost engine reports, with each team total matching too.
