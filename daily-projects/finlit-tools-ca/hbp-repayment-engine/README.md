# HBP Repayment & Refinancing Strategy Engine

> Models a 15-year Home Buyers' Plan repayment cycle so Canadians can see the long-term cash, tax, and lost-RRSP-room cost of skipping repayments.

## What it does
- **15-Year Projection**: year-by-year amortization under your chosen strategy.
- **Tax Bracket Thermometer**: auto-focuses on your worst tax year, showing where the skipped repayment lands across combined federal + provincial brackets, including bracket creep.
- **Cumulative Outcome Cards**: 15-year cash, full CRA tax bill, and percentage of your $60K lifetime HBP capacity that gets permanently destroyed.
- **Future Value at Retirement**: what the destroyed RRSP room would have been worth, compounded to retirement age.
- **Year-by-Year Table**: full breakdown, CSV exportable.

## Why it's useful
- Three strategy modes: Pay Every Year, Skip Every Year, or Custom (mark specific years).
- Per-year income overrides for parental leave, sabbatical, peak earnings.
- All 13 provinces and territories with surtaxes and Quebec's 16.5% federal abatement baked in.
- Bracket-aware: tax on a skipped repayment is computed band-by-band, not as a flat marginal rate.
- Grace-period aware: knows about the Budget 2024 5-year extension for 2022–2025 withdrawals.

## How to run it
Double-click `index.html`. Or use the hosted hub at the repo root.

## How to use it
1. Enter your outstanding HBP balance.
2. Pick an income archetype or enter an exact income.
3. Pick your province.
4. Choose a strategy mode (Pay All / Skip All / Custom).
5. If Custom, mark the years you'd skip and override any year's income.
6. Read the thermometer and cumulative cards. Export CSV if useful.

## Canadian rules it follows
| Rule | Value |
|---|---|
| HBP lifetime withdrawal cap | $60,000 (Budget 2024) |
| Repayment period | 15 years (1/15 annually) |
| Standard grace period | 2 years |
| Budget 2024 grace extension | 5 years for 2022–2025 withdrawals |
| Quebec abatement | 16.5% federal credit |
| Surtaxes | Ontario, PEI included |

## What it does NOT model
- The basic personal amount and other non-refundable credits.
- Capital gains, dividends, or RRSP/TFSA contributions in the same year.
- Income tax owed on eventual RRSP withdrawals (future-value figures are gross).
- Provincial low-income credits.
- HBP top-up withdrawals mid-cycle.

## Tech notes
One self-contained HTML file. React 18 via CDN, Tailwind via CDN, inline SVG thermometer, Babel in-browser. Inputs persist in `localStorage`.

## Disclaimer
Illustrative only. Federal and provincial brackets shift annually with indexation. Verify your HBP balance and required minimum in **CRA My Account** and consult a qualified accountant or CFP before deciding to skip a repayment. Not tax, legal, or investment advice.
