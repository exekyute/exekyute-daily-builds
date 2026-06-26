# Asset register rollforward

## Purpose
Rebuilds the CCA pool for each class straight from the asset register and the
opening balances, then checks it ties to the depreciation engine to the cent. A
fixed-asset accountant runs it as an independent second pass over the same data:
if the SQL rollforward and the Python engine agree, the year-end CCA numbers are
trustworthy.

## Inputs
- `sample_assets.csv`, the same asset register the engine reads. The runner uses
  asset_id, description, cca_class, capital_cost, in_service_date, disposed, and
  disposal_proceeds; the remaining columns are ignored here.
- `opening_ucc.csv`, the opening undepreciated capital cost per class.
- `per_class_cca.csv`, the engine output, used only to reconcile against.
- `schema.sql` seeds the CRA class rate table; `queries.sql` holds the rollforward
  queries.

## Validation rules
- Every required register column must be present.
- `disposed` must be Y or N.
- `capital_cost` and `disposal_proceeds` must be numbers; `capital_cost` cannot be negative.
- Every `cca_class`, in both the register and the opening balances, must be one of
  the seeded CRA classes. An unknown class is rejected.
- Opening UCC must be a number and cannot be negative.
- The engine file must be present; the runner reports if it is missing.

## Logic
Money is stored in the database as integer cents so the aggregation is exact. The
queries derive, per class:
- Opening UCC from the opening balances.
- Additions: the capital cost of assets placed in service in the tax year.
- Disposals: for each disposed asset, the lesser of proceeds and capital cost, summed.
- The count of assets in the class and the count still held at year end.

The runner converts those to decimal dollars and applies the pool rules, rounding
CCA half up to the cent:
1. UCC before CCA = opening + additions - disposals.
2. Negative pool gives recapture and resets to zero.
3. Positive pool with no assets left gives a terminal loss and resets to zero.
4. Otherwise the half-year rule holds back half of net additions, CCA = rate times
   the base, and closing UCC = UCC before CCA less CCA.

The rate math is done in the runner with `decimal.Decimal` rather than in SQL, so
the rounding matches the engine exactly. The pool rules are written out here
independently of the engine, so the reconciliation is a real cross-check.

## Outputs
Printed to the console: the rollforward table by class (opening, additions,
disposals, CCA, recapture, terminal loss, closing), the disposal detail, the check
results, and a final PASS or FAIL line. The runner exits non-zero on FAIL or on
rejected input.

## Edge cases
The sample register exercises a clean class with a half-year addition (class 8), a
disposal that triggers recapture (class 10), a disposal that triggers a terminal
loss (class 50), and a zero pool (class 12). `sample_assets_bad.csv` carries an
unknown class and a negative cost for the rejection path.

Hand-checked example, class 8, matching the engine in
`../01-cca-depreciation-engine`:

- Opening UCC 10,000.00 + additions 5,000.00 - disposals 0.00 = 15,000.00 before CCA.
- Half-year adjustment 2,500.00, so the base is 12,500.00.
- CCA = 20% x 12,500.00 = 2,500.00.
- Closing UCC = 15,000.00 - 2,500.00 = 12,500.00.

The runner also confirms class 10 recapture of 3,000.00 and class 50 terminal loss
of 900.00, and that the pool identity holds for every class.
