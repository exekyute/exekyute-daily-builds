# Spec: Tiered Commission Calculator

## Purpose

Turn one revenue figure and a commission plan into a payout, and show how the
payout was built. The plan is split into marginal tiers, the same way income
tax brackets work: each slice of revenue earns the rate of the tier it falls
in. Revenue above the quota threshold earns its tier rate multiplied by the
plan's accelerator. The result is an auditable breakdown a reviewer can re-add
by hand.

## Inputs

- **Revenue for the period**, in US dollars. Entered as text; dollar signs,
  commas, and surrounding spaces are tolerated.
- **A commission plan**, made of:
  - `quota`: the dollar threshold above which the accelerator applies.
  - `accelerator`: a multiplier of 1.0 or more, applied to commission earned on
    revenue above quota.
  - `tiers`: an ordered list, each with `label`, `from`, `to` (blank or `null`
    for the open top tier), and `rate` as a percent.

The plan is pre-filled with the bundled sample so the tool works on open. It can
be edited in the form, or replaced by loading a plan file. The file is read in
the browser with the `FileReader` API and never sent anywhere.

Default plan file: `data/sample_plan.json`.

## Validation rules

The calculation is refused, with every problem listed at once, if any of these
fail:

- Revenue parses as a number and is 0 or greater.
- `quota` is a number greater than 0.
- `accelerator` is a number of 1.0 or more.
- Every tier `rate` is greater than 0.
- Every tier `from` is 0 or greater, and `to` is greater than `from`.
- Only the last tier may be open ended (`to` blank or `null`).
- Tiers run in order with no gap and no overlap: each tier's `to` equals the
  next tier's `from`.

These are the calculator's own guard. The Comp Plan Rule Validator (tool 3)
holds the full, formal version of the same rules and is meant to be run on a
plan before it reaches this tool.

## Logic

All money is handled in integer cents. Rates become basis points (5% becomes
500) and the accelerator becomes thousandths (1.5 becomes 1500), so every figure
is computed with integer arithmetic.

For each tier, working in cents:

- `bandRevenue = max(0, min(revenue, tier.to) - tier.from)` is the revenue that
  falls inside the tier.
- The band is split at the quota line. `belowPortion` is the part at or below
  quota; `abovePortion` is the rest.
- `belowCommission = round(belowPortion * rateBp / 10000)`.
- `aboveCommission = round(abovePortion * rateBp * accelMilli / (10000 * 1000))`.
- The tier's payout is the sum of the two; each is rounded once.

The total payout is the sum of every tier's payout. Amounts are formatted with
`Intl.NumberFormat` so they print to the cent with no floating point artifacts.

## Outputs

- A breakdown table: tier, band range, revenue in band, the below-quota
  commission (with the portion and rate that produced it), the above-quota
  commission (with portion, rate, and accelerator), and the tier payout.
- A grand total payout.
- A one line summary: revenue, quota, and the accelerator in force.

## Edge cases

- **The hand-checked payout.** Plan: quota `$80,000`, accelerator `1.5`, tiers
  5% / 8% / 10% at `$0` / `$50,000` / `$100,000`. Revenue `$120,000` pays
  exactly **`$10,300.00`**:
  - Tier 1: `$50,000` at 5% = `$2,500.00` (all below quota).
  - Tier 2: `$30,000` at 8% = `$2,400.00` below quota, plus `$20,000` at 8% x
    1.5 = `$2,400.00` above quota, for `$4,800.00`.
  - Tier 3: `$20,000` at 10% x 1.5 = `$3,000.00` (all above quota).

  Because quota at `$80,000` sits inside Tier 2, this one example exercises a
  below-quota-only band, a band that straddles quota, and an above-quota-only
  band. The Comp Plan Rule Validator approves this same plan, so the two tools
  agree on `$10,300.00`. The figure is asserted in `tests.html`.
- **Zero revenue.** Pays `$0.00`; every tier shows an empty band.
- **Revenue below quota.** No tier accelerates; `$40,000` pays `$2,000.00` at
  the Tier 1 rate.
- **Revenue at a tier boundary.** `$50,000` fills Tier 1 exactly and leaves
  Tier 2 empty, paying `$2,500.00`.
- **Bad input.** A negative revenue, a zero rate, a tier gap, or a tier overlap
  is rejected with a specific message instead of producing a wrong payout.
