# Freight Allocation Toolkit

A personal project, one of several I build to model real-world job descriptions and
turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a landed-cost analyst in inbound logistics does,
while strengthening my foundational software development skills.

The repository holds two small tools that share one job: spread a shipment's freight
charge across its line items and reconcile to the carrier total exactly, then present
a clear, auditable breakdown. The first is a Python command-line allocator and the
second is a browser dashboard written in plain HTML, CSS, and vanilla JavaScript, so
the repository shows two languages while staying entirely no-backend. Both are
self-contained and rule-based, with the rules written out in each spec. All sample
data is synthetic.

## The tools

1. **[Freight Cost Allocator](01-freight-cost-allocator/)** is a Python tool
   (standard library) that allocates a freight charge across line items by weight or
   value and writes a landed-cost CSV. It uses `decimal.Decimal` with round-half-up
   in whole cents, then applies the largest-remainder method so rounding never adds
   or drops a cent against the freight total.
2. **[Shipment Landed-Cost Dashboard](02-shipment-landed-cost-dashboard/)** loads the
   landed-cost CSV in the browser and shows per-line costs with reconciled totals,
   summing in whole cents and formatting once with `Intl.NumberFormat` so totals
   never show floating-point artifacts.

## How they connect

The allocator produces a landed-cost CSV. The dashboard loads that same CSV. The two
are designed around one worked example so the handoff is verifiable end to end.
Allocating a $100.00 freight charge by value across the sample shipment:

| line | quantity | unit cost | allocated freight | landed unit cost |
|------|----------|-----------|-------------------|------------------|
| L001 | 7        | $5.00     | $25.93            | $8.70            |
| L002 | 3        | $10.00    | $22.22            | $17.41           |
| L003 | 5        | $4.00     | $14.81            | $6.96            |
| L004 | 2        | $0.00     | $0.00             | $0.00            |
| L005 | 1        | $50.00    | $37.04            | $87.04           |

The per-line allocations sum to exactly $100.00. Loading the resulting CSV, the
dashboard reports the same total freight allocated of $100.00 and a total landed cost
of $235.00 (goods value $135.00 plus freight $100.00). The allocator's console
summary and the dashboard's totals agree.

## Running the tools

The Freight Cost Allocator runs with Python from its folder (standard library only),
and the dashboard opens by double-clicking its `index.html` and loading the CSV. Each
tool folder has its own README with run instructions and screenshots, a `spec.md`,
and a test run you can see pass (a `unittest` suite for the allocator, a `tests.html`
page for the dashboard).

## Repository layout

```
freight-allocation-toolkit/
├── 01-freight-cost-allocator/         Python command-line allocator
└── 02-shipment-landed-cost-dashboard/ browser dashboard
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
