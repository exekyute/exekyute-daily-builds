# Procurement Landed Cost

## Purpose
Turns a brewery's raw material and packaging purchase orders into a landed cost
per line, folding freight and Canadian import duty into the price paid. A cost
accountant runs it at the start of month-end so every later tool, batch costing,
valuation, and margin, starts from the true cost of materials rather than the
invoice price alone.

## Inputs
One purchase-order CSV, one row per order line, with these columns:

| Column | Type | Notes |
| --- | --- | --- |
| po_id | text | Purchase order number. Lines sharing a po_id share one freight bill. |
| line_id | text | Line number within the order. Unique with po_id. |
| date | text | ISO date, recorded but not used in the math. |
| sku | text | Stock-keeping unit the line buys. |
| description | text | Plain name carried through to the output. |
| category | text | `raw_material` or `packaging_material`. |
| quantity | number | Greater than zero, in the SKU's stock unit. |
| unit | text | Stock unit: `kg`, `each`, and so on. |
| unit_price | number | Price per unit on the invoice, before freight and duty. |
| freight_total | number | Total freight for the whole order. The same figure on every line of the order. |
| duty_rate | number | Import duty as a percent of the line's value. Zero for domestic goods. |

## Validation rules
The file is rejected, with nothing written, if any row fails a check. Each
failure names the row and the problem:

- A required column is missing from the header.
- `po_id` or `line_id` is blank.
- A `po_id`/`line_id` pair repeats an earlier one.
- `sku` or `unit` is blank.
- `category` is not `raw_material` or `packaging_material`.
- `quantity` is not a number, or is zero or negative.
- `unit_price`, `freight_total`, or `duty_rate` is non-numeric or negative.
- Two lines of the same order record different `freight_total` figures.

## Logic
1. Group the lines by `po_id` in the order each order first appears.
2. For each order, compute every line's extended value: quantity times unit price.
3. Allocate the order's `freight_total` across its lines in proportion to extended value, using the largest-remainder method: each line takes the floor of its proportional share in cents, then the leftover cents go one at a time to the lines with the largest fractional remainder, so the allocated freight sums back to the freight total exactly. When every line on an order has a zero extended value, the freight is spread as evenly as cents allow.
4. Charge import duty per line: the line's extended value times `duty_rate` percent.
5. The landed total of a line is its extended value plus allocated freight plus duty. The landed unit cost is the landed total divided by quantity.

Money is held as `decimal.Decimal` and rounded half up to the cent. Landed unit
cost is shown to four decimal places.

## Outputs
`landed_costs.csv`, one row per purchase-order line, with `po_id`, `line_id`,
`sku`, `description`, `category`, `quantity`, `unit`, `unit_price`,
`extended_value`, `freight_alloc`, `duty`, `landed_total`, and
`landed_unit_cost`. The batch costing tool and the perpetual valuation tool both
read this file.

## Edge cases
The sample data is built to exercise each branch:

- **Even freight split** on an order whose two lines have equal value (PO-1001, malt and cans, $150.00 each).
- **Largest-remainder split** where the proportional shares do not land on whole cents (PO-1003, keg and label, $76.42 and $13.58 from a $90.00 bill).
- **Imported receipt** carrying import duty in the landed cost (PO-1002, Cascade hops at a 6% rate).
- **Single-line order** where one line takes the whole freight bill (PO-1002).
- **Second receipt of an existing SKU** at a different price, so the period shows more than one malt cost (PO-1004).
- A separate `sample_purchase_orders_invalid.csv` carries a duplicate line key, a negative quantity, a bad category, a non-numeric price, a negative freight, and two lines of one order that disagree on freight, so the rejection path can be seen.

### Hand-checked example
PO-1003 splits a $90.00 freight bill across two lines:

- Keg line: 100 kegs at $45.00 = $4,500.00 extended.
- Label line: 40,000 labels at $0.02 = $800.00 extended.
- Order value = $5,300.00. The keg share is 90 times 4,500 / 5,300 = $76.4151, the label share is 90 times 800 / 5,300 = $13.5849. Floored to the cent that is $76.41 and $13.58, which sum to $89.99, so the leftover cent goes to the keg line (the larger remainder): keg $76.42, label $13.58.
- Keg landed total = $4,500.00 + $76.42 = $4,576.42, unit cost $45.7642. Label landed total = $800.00 + $13.58 = $813.58, unit cost $0.0203.

PO-1002 imports hops: 200 kg at $18.00 = $3,600.00, freight $120.00 all to the
one line, duty 6% of $3,600.00 = $216.00, landed total $3,936.00, unit cost
$19.6800.

Total landed cost across the six lines = **$18,126.00**, of which $510.00 is
freight and $216.00 is import duty. This total is checked by `test_landed.py`,
and the per-SKU landed costs flow into the batch costing and valuation tools.
