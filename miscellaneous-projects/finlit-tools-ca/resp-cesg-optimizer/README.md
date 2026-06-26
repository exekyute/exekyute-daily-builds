# RESP + CESG Optimizer

> Projects a Canadian RESP year by year, contributions, CESG grant, and growth, toward a 4-year tuition target.

## What it does
- **RESP balance at age 18**: how much will actually be there for tuition.
- **Total CESG received**: free government grant captured.
- **Total contributions**: how much of your own money went in.
- **Tuition goal progress**: what % of your target the projection covers, with the exact shortfall or surplus called out.
- **Balance Growth Over Time** chart, line + stacked area showing contributions, grant, and growth.
- **"Whose Money Is It?" bar**: final balance split into your cash, government grant, and market growth.

## Why it's useful
- Enforces the $50K lifetime contribution cap and the $7,200 lifetime CESG cap.
- Implements the 16–17 special eligibility rule (most public calculators skip it).
- Nudges you toward the $2,500/yr sweet spot that captures the full $500 annual grant.
- Auto-saves; CSV export of the year-by-year schedule; printer-friendly.

## How to run it
Double-click `index.html`. Or use the hosted hub at the repo root.

## How to use it
1. Slide your child's current age.
2. Slide your annual contribution.
3. Slide your expected return rate.
4. Slide your 4-year tuition target.
5. Read the progress bar, the chart, and the year-by-year table. Export CSV if useful.

## Canadian rules it follows
| Rule | Value |
|---|---|
| CESG match rate | 20% of contributions |
| Annual CESG room | $500/yr ($1,000/yr if catching up unused room) |
| Lifetime CESG cap | $7,200 per beneficiary |
| Lifetime RESP contribution cap | $50,000 per beneficiary |
| CESG eligibility ends | Dec 31 of the year the child turns 17 |
| 16–17 rule | $2,000 contributed before age 16, OR at least $100 in any 4 prior years |

## What it does NOT model
- Additional CESG (income-based bonus for lower-income families).
- Canada Learning Bond.
- Provincial grants (QESI for Quebec, BCTESG for British Columbia).
- Family-plan RESPs with multiple beneficiaries.
- Withdrawal phase / Educational Assistance Payments.
- Over-contribution penalties.

## Tech notes
One self-contained HTML file. React 18 via CDN, Chart.js via CDN, Tailwind via CDN, Inter font, Babel in-browser. Has a built-in math test suite that runs on page load, open DevTools (F12) → Console to see results. Inputs persist in `localStorage`.

## Disclaimer
Illustrative only. The 16–17 eligibility check uses only contributions made inside the simulation, real-world prior contributions are not accounted for. Verify in **CRA My Account** and consult a qualified financial advisor before acting. Not tax, legal, or investment advice.
