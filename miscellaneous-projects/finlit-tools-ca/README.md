# Canadian FinLit Tools

Seven self-contained, browser-based calculators for Canadian benefit and tax rules. Each one turns a piece of normally opaque math, a CCB phase-out, a CESG window, an RRSP clawback, into a tool you can see and change, and each lives in a single HTML file with no build step because the rules themselves are the hard part.

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

Each tool links from the hub at the repo root (`index.html`) and back to it via a **Home** button.

## How to run

- **Locally:** open `index.html` at the repo root in any modern browser. Each tool also runs by double-clicking its own `index.html`.
- **Hosted:** push to GitHub and enable Pages (Settings, then Pages, then Deploy from branch, `main` and root). The relative links work in both modes.

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

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
