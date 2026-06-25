# Spec: Comp Plan Rule Validator

## Purpose

Check a commission plan before it is used for a pay cycle. The page flags gaps,
overlaps, zero or negative rates, and thresholds that run out of order, so a
broken plan is caught before it reaches the calculator. It checks the same plan
format the Tiered Commission Calculator consumes, which means a plan approved
here is safe to pay against there.

## Inputs

- A commission plan, made of:
  - `quota`: the dollar threshold above which the accelerator applies.
  - `accelerator`: a multiplier applied to commission above quota.
  - `tiers`: an ordered list, each with `label`, `from`, `to` (blank or `null`
    for the open top tier), and `rate` as a percent.

The plan is pre-filled with the approved sample. It can be edited in the form,
loaded from a `.json` file, or replaced with the bundled example that contains
problems. Files are read in the browser with the `FileReader` API and never sent
anywhere.

Bundled files: `data/sample_plan.json` (approved) and `data/broken_plan.json`
(one of every problem).

## Validation rules

Each problem becomes a finding with a severity, a location, and a message. A
plan with no error findings is reported as approved.

Errors:

- **Quota** is missing, not a number, or not greater than 0.
- **Accelerator** is missing, not a number, or below 1.0 (which would cut pay
  above quota).
- **No tiers** in the plan.
- **Tier from** is missing, not a number, or negative.
- **Tier to** is missing on a non-top tier, or is not a number.
- **Out-of-order threshold**: a tier's `to` is not greater than its `from`.
- **Tier rate** is missing, not a number, or not greater than 0.
- **First tier start**: the first tier does not start at 0, leaving the bottom
  of the range uncovered.
- **Gap**: a tier's `to` does not meet the next tier's `from`, so a band of
  revenue is uncovered.
- **Overlap**: a tier's `to` runs past the next tier's `from`, so two tiers
  claim the same revenue.
- **Duplicate tier label**.

Warning (does not block approval):

- **Closed top tier**: the top tier has an upper bound, so revenue above it
  would earn nothing. This is allowed but called out in case it was not
  intended.

## Logic

The rules are pure functions over the plan object. `validate(plan)` returns
`{ approved, findings }`, where `findings` is a list of
`{ severity, code, location, message }` and `approved` is true when no finding
has severity `error`. The page renders the findings in a table and shows a green
banner when the plan is approved.

## Outputs

- A green **Plan approved** banner when there are no errors.
- A findings table otherwise: severity badge, location (the plan or a specific
  tier), and a plain message. A heading counts the errors and warnings.

## Edge cases

- **The approved sample agrees with the calculator.** `data/sample_plan.json` is
  the same plan, byte for byte, that the Tiered Commission Calculator ships in
  its own `data` folder. It passes every check here. Run through that tool with
  revenue `$120,000`, it pays exactly **`$10,300.00`** (Tier 1 `$2,500.00`,
  Tier 2 `$4,800.00`, Tier 3 `$3,000.00`). The validator approving this plan and
  the calculator producing that payout are two views of the same agreed plan.
- **One file, every flag.** `data/broken_plan.json` trips a zero quota, an
  accelerator below 1.0, a zero rate, a negative rate, an out-of-order
  threshold, an overlap, and a gap, all reported from a single check.
- **A warning is not a rejection.** A plan whose only issue is a closed top tier
  is still approved, with the closed tier noted.
