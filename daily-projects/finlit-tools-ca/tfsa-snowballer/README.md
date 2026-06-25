# TFSA Snowballer

> Shows the gap between tax-free TFSA compounding and a taxable account holding the same investments, year by year.

## What it does
- **Final TFSA Balance**: total tax-free cash at withdrawal age.
- **Taxable Alternative**: what the same contributions would yield outside a TFSA.
- **Total Lost to Taxes**: the gap between the two.
- **Portfolio Composition Bar**: contributions vs. tax-free growth.
- **Year-by-Year Table**: running balances + lost-to-taxes column. CSV exportable.

## Why it's useful
- Surfaces tax drag as a single dollar number, not a hand-wave.
- Built-in CRA warning steers users away from over-contribution (1%/month penalty).
- Slide your current balance from zero; everything updates live.

## How to run it
Double-click `index.html`. Or use the hosted hub at the repo root.

## How to use it
1. Set your current TFSA balance.
2. Set your current and withdrawal ages.
3. Set your monthly contribution.
4. Set your expected return rate.
5. Set your annual income (drives the tax-drag estimate).
6. Read the composition bar and the year-by-year table. Export CSV if useful.

## Canadian rules it follows
- TFSA growth is fully tax-free.
- The taxable comparison assumes a tax-drag of 50% of your marginal rate applied to annual growth, a blend approximating mixed interest, dividends, and capital gains.
- Marginal rate uses a 5-band simplified combined federal+provincial scale.

## What it does NOT model
- Province-specific brackets or surtaxes.
- Foreign-withholding tax inside the TFSA (e.g. US dividends).
- Withdrawal-and-recontribution timing rules.
- The 1%/month over-contribution penalty.
- Successor-holder / beneficiary transfers.
- Inflation-adjusted real returns.

## Tech notes
One self-contained HTML file. React 18 via CDN, Tailwind via CDN, Inter font, Babel in-browser. Inputs persist in `localStorage` (key `tfsa_user_inputs_final`).

## Disclaimer
Illustrative only. Verify your exact TFSA contribution room in **CRA My Account** before contributing real money and consult a Certified Professional Accountant for tax planning. Not tax, legal, or investment advice.
