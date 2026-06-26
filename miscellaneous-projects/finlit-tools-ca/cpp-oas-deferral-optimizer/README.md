# CPP & OAS Deferral Optimizer

> Helps Canadians choose what age to start CPP and OAS by projecting lifetime payout under different start ages.

## What it does
- **Total Monthly Pension**: combined CPP + OAS at the start ages you pick.
- **Lifetime Value**: cumulative cash through your expected lifespan.
- **Composition Breakdown**: visual bar splitting lifetime cash into CPP vs. OAS.
- **Cumulative Cash Table**: age-by-age running totals, CSV exportable.

## Why it's useful
- Translates the dense early/late penalty/bonus rulebook into a drag-and-drop interface.
- Lets you plug in your own Service Canada estimates rather than relying on national averages.
- Future-proof against rate updates: bonus and penalty percentages are applied to whatever base you enter.

## How to run it
Double-click `index.html`. Or use the hosted hub at the repo root.

## How to use it
1. Enter your estimated base CPP (at age 65) and base OAS from your Service Canada account.
2. Slide CPP and OAS start ages.
3. Slide your expected lifespan.
4. Read the totals and the composition bar; export the schedule if useful.

## Canadian rules it follows
| Rule | Value |
|---|---|
| Early CPP penalty | 0.6% per month before age 65 |
| Late CPP bonus | 0.7% per month after age 65 (until 70) |
| Late OAS bonus | 0.6% per month after age 65 (until 70) |
| OAS earliest start | Age 65 |

## What it does NOT model
- Future inflation or time-value-of-money discounting.
- OAS recovery tax (clawback) at higher incomes.
- Marital or survivor benefits.
- Post-65 CPP contributions.
- Partial-residency OAS adjustments.
- Tax owed on benefits received.

## Tech notes
One self-contained HTML file. React 18 via CDN, Tailwind via CDN, Inter font, Babel in-browser. Inputs persist in `localStorage`.

## Disclaimer
Illustrative only. Real entitlement depends on your full contribution and residency history. Verify in **My Service Canada Account** and consult a qualified financial advisor before deferring. Not tax, legal, or investment advice.
