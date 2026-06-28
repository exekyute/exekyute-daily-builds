# COGS and SKU Profitability

## Purpose
Combines production cost and excise duty into a cost of goods sold for every
sales line, then reports revenue and gross margin by SKU, product line, and
sales channel. A cost accountant runs it to see which beers and which channels
carry the period.

## Inputs
Three files:

`finished_unit_costs.csv` (from the batch tool): the production cost and packaged
volume of each finished good. Columns used: `fg_sku`, `product_line`,
`abv_class`, `units`, `packaged_litres`, `line_cost`.

`excise_summary.csv` (from the excise tool): `abv_class`, `excise_duty`.

`sales.csv`, one row per SKU and channel:

| Column | Type | Notes |
| --- | --- | --- |
| fg_sku | text | Must have been produced this period. |
| channel | text | `retail`, `on_premise`, or `distributor`. |
| units_sold | number | Whole number greater than zero. |
| unit_price | number | Selling price per unit, greater than zero. |

## Validation rules
The sales file is rejected, with nothing written, if any check fails:

- A required column is missing from the header.
- A `fg_sku` was not produced this period.
- `channel` is not one of the three allowed values.
- `units_sold` is not a whole number greater than zero.
- `unit_price` is non-numeric, or zero or negative.
- The total units sold for a SKU exceed the units produced (there is no finished-goods opening balance).

## Logic
1. From the finished-unit costs, total packaged litres by ABV class. Divide each class's excise duty by its packaged litres to get an excise rate per litre.
2. For each finished good, work out the production cost per unit (the batch line cost divided by units made) and the excise per unit (the class rate per litre times the litres in one unit).
3. For each sales line: revenue is unit price times units sold; production cost of goods is the production unit cost times units sold; excise cost of goods is the excise per unit times units sold; total cost of goods is the two added. Gross margin is revenue minus total cost of goods, and margin percent is gross margin over revenue.
4. Roll the lines up by product line and by channel.

Money is held as `decimal.Decimal` and rounded half up to the cent. Per-unit
production cost and excise are kept at full precision and quantized once per line.

## Outputs
`sku_margins.csv`, one row per sales line: `fg_sku`, `product_line`, `channel`,
`units_sold`, `unit_price`, `revenue`, `cogs_production`, `cogs_excise`,
`cogs_total`, `gross_margin`, `margin_pct`. The month-end close and the dashboard
read it.

## Edge cases
The sample data exercises each branch:

- **One SKU sold through two channels** (FG-IPA-CAN, retail and distributor), so the product-line roll-up sums across channels.
- **Cans and kegs in one product line** at very different unit prices and margins (Lager, a $2.50 can and a $220.00 keg).
- **Both ABV classes**, so each picks up its own excise rate per litre.
- The invalid sample carries a SKU that was not produced, a bad channel, a quantity that exceeds production, and a zero price, so the rejection path can be seen.

### Hand-checked example
FG-LAGER-CAN sold retail, 2,500 cans at $2.50:

- Revenue = 2,500 times $2.50 = $6,250.00.
- Production cost per unit = $1,302.94 / 3,000 = $0.434313; times 2,500 = $1,085.78.
- Excise rate for the over 2.5% class = $114.01 / 3,025 L = $0.0376893 per litre; a can holds 0.355 L, so excise per unit = $0.0133797; times 2,500 = $33.45.
- Cost of goods = $1,085.78 + $33.45 = $1,119.23. Gross margin = $6,250.00 - $1,119.23 = $5,130.77, a margin of 82.09%.

Across all six sales lines: revenue **$25,435.00**, cost of goods **$5,404.81**,
gross margin **$20,030.19** (78.75%). These totals are checked by
`test_margin.py`, and the per-SKU figures feed the month-end close and the
dashboard.
