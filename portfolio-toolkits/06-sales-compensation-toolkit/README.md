# Sales Compensation Toolkit

A personal project, one of several I build to model real-world job descriptions
and turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a sales compensation analyst does, while
strengthening my foundational software development skills.

The repository holds three small browser tools written in plain HTML, CSS, and
vanilla JavaScript. Each one is self-contained, rule-based, and built around clean
business logic, careful input validation, and exact money math. There is no
framework, no build step, and no server: every tool opens by double-clicking its
HTML file, and any file you load is read in the browser with the `FileReader` API
and stays on your machine. Money is handled in integer cents and formatted with
`Intl.NumberFormat`, so amounts print to the cent with no floating-point
artifacts.

## The tools

1. **[Tiered Commission Calculator](01-tiered-commission-calculator/)** takes a
   revenue figure and a commission plan, splits the revenue across the plan's
   marginal tiers, applies the accelerator to the portion above quota, and shows
   how much each tier contributed to the payout.
2. **[Quota Attainment Dashboard](02-quota-attainment-dashboard/)** loads a CSV of
   rep results with the FileReader API and renders a color-coded table of who
   landed under, at, or over quota, with a team summary and a panel listing any
   rows that failed validation.
3. **[Comp Plan Rule Validator](03-comp-plan-rule-validator/)** checks a commission
   plan before a pay cycle, flagging gaps, overlaps, zero or negative rates, and
   thresholds that run out of order.

## How they connect

The Comp Plan Rule Validator checks the same plan format the Tiered Commission
Calculator consumes. Both ship the same plan file, `sample_plan.json`. The
validator approves that plan, and the calculator pays revenue of `$120,000`
against it as exactly `$10,300.00`, split `$2,500.00` in Tier 1, `$4,800.00` in
Tier 2, and `$3,000.00` in Tier 3. The hand-checked payout is documented in both
tools' `spec.md`. The Quota Attainment Dashboard stands on its own, covering the
separate job of tracking attainment across the team and flagging outliers.

## Running the tools

Open the tool's `index.html` in a web browser by double-clicking it. Nothing to
install. Each tool also has a `tests.html` that runs its logic against hand-worked
numbers and prints PASS or FAIL on the page, so the checks run with no build
tooling.

Each tool folder has its own README with worked examples and screenshots, and a
`spec.md` describing purpose, inputs, validation, logic, outputs, and edge cases.

## Repository layout

```
sales-compensation-toolkit/
  LICENSE
  README.md
  01-tiered-commission-calculator/
  02-quota-attainment-dashboard/
  03-comp-plan-rule-validator/
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
