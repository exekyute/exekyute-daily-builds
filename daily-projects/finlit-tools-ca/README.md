# Canadian FinLit Tools

> Seven self-contained, browser-based calculators for Canadian benefit and tax rules.

## The tools

| Tool | What it shows |
|---|---|
| [Benefit Clawback Radar](./benefit-clawback-radar/) | EMTR cliffs from CCB and GIS phase-outs, plus an RRSP escape hatch |
| [CPP & OAS Deferral Optimizer](./cpp-oas-deferral-optimizer/) | Lifetime payout vs. start age |
| [FHSA Optimization Engine](./fhsa-calculator/) | Tax-free home savings growth |
| [HBP Repayment Engine](./hbp-repayment-engine/) | 15-year cost of skipping HBP repayments |
| [LLP vs. Wealth Advisor](./llp-vs-wealth-advisor/) | Opportunity cost of withdrawing from RRSP for school |
| [RESP + CESG Optimizer](./resp-cesg-optimizer/) | Capturing the full $7,200 CESG grant |
| [TFSA Snowballer](./tfsa-snowballer/) | Tax-free vs. taxable account drift over time |

Each tool links from the hub at the repo root (`index.html`) and back to it via a **← Home** button.

## How to run

- **Locally:** open `index.html` at the repo root in any modern browser. Each tool also runs by double-clicking its own `index.html`.
- **Hosted:** push to GitHub and enable Pages (Settings → Pages → Deploy from branch → `main` / root). The relative links work in both modes.

## Why I built these (self-learning objectives)

I built these to refresh hands-on coding fundamentals while practicing the harder skill: explaining dense Canadian tax-and-benefit rules in plain language, with the rules themselves as the constraint that forces clarity.

Three things I wanted to get better at, in order:

1. **Refresh the basics**: Vanilla JS, React-via-CDN, single-file architecture, no build step. Forcing each tool to live in one HTML file removed every excuse to over-engineer.
2. **Explain rules without hand-waving**: If I can't translate a CCB phase-out tier or a CESG eligibility window into a working calculator, I don't actually understand it.
3. **Make the invisible visible**: Most Canadian benefit math is technically public but practically opaque (paystubs don't show clawbacks, CRA recalculates months later). A visual tool is the bridge.

## Code conventions

Each tool uses a Concise Operational Flow annotation style so the code reads like a workflow:

- `// OPS CONTEXT:` at the top of the script, one-line summary of the tool's real-world purpose.
- `// M1 [Name]:`, `// M2 [Name]:` … inline above each meaningful code block.
- `// PIVOT:` above any code where changing a CRA rule, bracket table, or phase-out threshold would break or alter the logic.

Math primitives are pure and isolated. The composition layers (RRSP-aware wrappers, strategy builders) feed adjusted inputs into the primitives without modifying them.

## Repo layout

```
finlit-tools-ca/
├── index.html                       # Hub page
├── README.md                        # This file
├── benefit-clawback-radar/
│   ├── index.html
│   └── README.md
├── cpp-oas-deferral-optimizer/
│   ├── index.html
│   └── README.md
├── fhsa-calculator/
│   ├── index.html
│   └── README.md
├── hbp-repayment-engine/
│   ├── index.html
│   └── README.md
├── llp-vs-wealth-advisor/
│   ├── index.html
│   └── README.md
├── resp-cesg-optimizer/
│   ├── index.html
│   └── README.md
└── tfsa-snowballer/
    ├── index.html
    └── README.md
```

## Disclaimer

These tools are illustrative only. They use 2026-indexed estimates of federal and provincial rules and simplify many real-world variables. Each tool's own README and in-app footer document what it does and does not model.

Verify your personal numbers in **CRA My Account** or **My Service Canada Account** and consult a Certified Professional Accountant or qualified financial advisor before acting. Not tax, legal, or investment advice.
