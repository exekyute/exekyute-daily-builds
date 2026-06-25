# Freight Allocation Toolkit

Two small, focused tools for landed-cost work in inbound logistics. One spreads a
shipment's freight charge across its line items and reconciles to the carrier
total exactly; the other reads that result in the browser and presents a clear,
auditable breakdown. Neither tool uses a backend, a database, or any build step,
and no data leaves your machine.

The two tools are written in different languages on purpose, to keep each one in
the simplest form for its job:

| # | Tool | Built with | What it does |
|---|------|------------|--------------|
| 1 | [Freight Cost Allocator](01-freight-cost-allocator/) | Python (standard library) | Allocates a freight charge across line items by weight or value and writes a landed-cost CSV. |
| 2 | [Shipment Landed-Cost Dashboard](02-shipment-landed-cost-dashboard/) | HTML, CSS, vanilla JavaScript | Loads the landed-cost CSV in the browser and shows per-line costs with reconciled totals. |

## How the two tools connect

The allocator produces a landed-cost CSV. The dashboard loads that same CSV. The
two are designed around one worked example so the handoff is verifiable end to
end.

Allocating a $100.00 freight charge by value across the sample shipment gives:

| line | quantity | unit cost | allocated freight | landed unit cost |
|------|----------|-----------|-------------------|------------------|
| L001 | 7        | $5.00     | $25.93            | $8.70            |
| L002 | 3        | $10.00    | $22.22            | $17.41           |
| L003 | 5        | $4.00     | $14.81            | $6.96            |
| L004 | 2        | $0.00     | $0.00             | $0.00            |
| L005 | 1        | $50.00    | $37.04            | $87.04           |

The per-line allocations sum to exactly $100.00. Loading the resulting CSV, the
dashboard reports the same total freight allocated of $100.00 and a total landed
cost of $235.00 (goods value $135.00 plus freight $100.00). The allocator's
console summary and the dashboard's totals agree.

## How the money math stays exact

- The allocator uses `decimal.Decimal` with round-half-up and works in whole
  cents, then applies the largest-remainder method so rounding never adds or
  drops a cent against the freight total.
- The dashboard converts every dollar amount to whole cents, sums in cents, and
  formats once with `Intl.NumberFormat`, so totals never show floating-point
  artifacts.

## Repository layout

```
freight-allocation-toolkit/
├── 01-freight-cost-allocator/         Python command-line allocator
│   ├── allocator_logic.py             Pure logic: parsing, validation, allocation
│   ├── cli.py                         Arguments, file I/O, table output
│   ├── test_allocator_logic.py        Unit tests
│   ├── data/                          Sample, invalid, and output CSVs
│   └── spec.md                        Full specification
└── 02-shipment-landed-cost-dashboard/ Browser dashboard
    ├── index.html                     Markup
    ├── styles.css                     Two-tone palette and spacing scale
    ├── dashboard_logic.js             Pure logic: parse, validate, total, format
    ├── app.js                         FileReader and rendering
    ├── tests.html                     In-page test harness
    ├── data/                          Sample and invalid CSVs
    └── spec.md                        Full specification
```

Each tool folder has its own README with run instructions and screenshots.

## About

This is a personal portfolio project, one of several I build to model real-world
job descriptions and practice applied problem-solving and foundational software
skills. Both tools are deterministic and rule-based.

## License

Released under the [MIT License](LICENSE).
