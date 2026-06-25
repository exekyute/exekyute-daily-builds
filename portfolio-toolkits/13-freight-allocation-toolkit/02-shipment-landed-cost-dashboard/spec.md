# Spec: Shipment Landed-Cost Dashboard

## Purpose

Load the landed-cost CSV produced by the Freight Cost Allocator (in the browser,
with no upload and no server) and present a clear per-line landed-cost breakdown
plus reconciled totals, so inventory and finance can read the allocation and
confirm it ties back to the freight charge.

## Inputs

- A landed-cost CSV chosen with a file picker and read with the `FileReader` API.
  Expected header: `line_id`, `description`, `quantity`, `unit_cost`,
  `allocated_freight`, `landed_unit_cost`. A sample is included at
  `data/landed_cost.csv`. The file is read locally and never sent anywhere.

## Validation rules

- A file must be chosen before anything renders.
- The header must contain all required columns; any missing ones are named.
- The file must have at least one data row.
- `quantity` parses as a whole number greater than 0.
- `unit_cost`, `allocated_freight`, and `landed_unit_cost` parse as money 0 or
  greater (a plain decimal with up to two places).
- Bad rows are reported by line number rather than silently dropped. If any row
  is invalid, the table is not drawn and every problem is listed.

## Logic

All logic lives in `dashboard_logic.js` as pure functions with no DOM access:
`parseCsv`, `missingColumns`, `toCents`, `parseQuantity`, `buildRows`,
`summarize`, and `formatMoney`.

- Money strings are parsed straight into integer cents (for example `25.93`
  becomes `2593`) without floating-point arithmetic.
- Per line, goods value cents is `quantity * unit_cost_cents`; line landed cost
  cents is `goods value + allocated_freight`.
- Totals are summed in cents and formatted once for display with
  `Intl.NumberFormat`, so no floating-point artifacts can appear.
- Summary figures: total goods value, total freight allocated
  (`sum(allocated_freight)`), and total landed cost (`sum(line landed cost)`).

## Outputs

- A table of each line: line, description, quantity, unit cost, allocated
  freight, landed unit cost.
- Summary cards: line count, total goods value, total freight allocated, total
  landed cost.
- A status line confirming the file loaded and that the total freight allocated
  ties back to the carrier charge.

Styling uses a two-tone palette (one base plus one accent) defined as CSS
variables, and one spacing scale of 8px multiples reused for every margin,
padding, and gap, so inputs, buttons, rows, and cells stay evenly and roomily
spaced on a shared grid.

## Connection to the allocator (hand-checked example)

The sample at `data/landed_cost.csv` is the exact output of the allocator's
`--freight 100.00 --basis value` run:

| line | quantity | unit cost | allocated freight | landed unit cost |
|------|----------|-----------|-------------------|------------------|
| L001 | 7        | $5.00     | $25.93            | $8.70            |
| L002 | 3        | $10.00    | $22.22            | $17.41           |
| L003 | 5        | $4.00     | $14.81            | $6.96            |
| L004 | 2        | $0.00     | $0.00             | $0.00            |
| L005 | 1        | $50.00    | $37.04            | $87.04           |

Loading it, the dashboard reports **total freight allocated $100.00**, which
matches the freight charge the allocator started from exactly, and **total
landed cost $235.00** (goods value $135.00 plus freight $100.00). These are the
same figures the allocator's own summary line shows, which proves the two tools
agree end to end.

## Edge cases

- Choosing a file with a missing required column names the missing column and
  draws nothing.
- A CSV with a header but no data rows is reported, not rendered as an empty
  table.
- Rows with a bad quantity or a non-numeric money field are listed by line
  number; the table is withheld until the data is clean.
- The zero-value promo line (L004) shows $0.00 across the board and contributes
  nothing to the totals, matching the allocator.
