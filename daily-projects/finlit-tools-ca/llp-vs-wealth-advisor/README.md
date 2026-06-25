# LLP vs. Wealth Advisor

> Shows the lifelong opportunity cost of pulling RRSP money under the Lifelong Learning Plan, even with perfect repayment, the years out of the market never come back.

## What it does
- **Opportunity Cost Gap**: the dollar gap between "untouched RRSP" and "withdrew + repaid on schedule" at Year 25.
- **Gap as % of Tuition**: the headline gap expressed as a percentage of the tuition you withdrew.
- **Divergence Chart**: two curves diverging year by year, with phase markers (school / grace / repayment / growth) and a hover-to-inspect tooltip.
- **Real-World Equivalents**: the gap translated into months of groceries, multiples of a wedding, and years of rent.
- **Year-by-Year Table**: full breakdown, CSV exportable.

## Why it's useful
- Three education archetypes: Micro-Credential ($5K), 1-Year Post-Grad ($10K), 2-Year Career Pivot ($20K).
- Three growth assumptions: 5% / 6.5% / 8%.
- Optional age input translates "Year 25" into your real age at withdrawal.
- Grace-period toggle lets you compare CRA's 5-year default to immediate repayment.

## How to run it
Double-click `index.html`. Or use the hosted hub at the repo root.

## How to use it
1. Pick an education scenario.
2. Pick a growth rate.
3. Toggle the grace period on or off.
4. Optionally enter your age today.
5. Read the gap. Hover the chart to inspect any year. Export CSV if useful.

## Canadian rules it follows
| Rule | Value |
|---|---|
| Maximum annual LLP withdrawal | $10,000 |
| Lifetime LLP participation limit | $20,000 |
| Repayment period | 10 years (1/10 annually) |
| Repayment designation | Schedule 7 of T1 |
| Tax deduction on repayments | None |

**Grace period model:** when toggled on, repayments start 5 years after the last withdrawal year. The actual CRA rule is the earlier of (a) the 5th year after your first LLP withdrawal, or (b) the 2nd year after you cease to be a full-time student, so your real schedule may begin sooner.

## What it does NOT model
- Variable annual returns (uses a constant rate).
- Late or missed repayments (treated as income inclusion in the real world).
- Partial-year repayments or accelerated repayment.
- LLP combined with HBP withdrawals.
- Investment growth tax inside non-registered accounts.

## Tech notes
One self-contained HTML file. Vanilla JavaScript, custom CSS, inline SVG chart, Inter font via Google Fonts. Inputs persist in `localStorage` (key `llp_state_v1`).

## Disclaimer
Illustrative only. Real-world equivalent anchors are rough Canadian averages from Statistics Canada food expenditure data, industry surveys, and rental market reports. Verify your LLP balance and repayment schedule in **CRA My Account** and consult a qualified professional before acting. Not tax, legal, or investment advice.
