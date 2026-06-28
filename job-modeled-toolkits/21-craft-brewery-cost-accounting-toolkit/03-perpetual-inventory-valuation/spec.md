# Perpetual Inventory Valuation

## Purpose
Keeps a perpetual weighted-average ledger across raw materials, packaging, and
finished goods, and reports the on-hand quantity, unit cost, and dollar value of
every SKU at the end of the period. A cost accountant runs it to produce the book
inventory the month-end close reconciles against the physical count.

## Inputs
One transaction CSV, one row per inventory movement, in the order the movements
happened:

| Column | Type | Notes |
| --- | --- | --- |
| txn_id | text | Unique across the file. |
| date | text | ISO date, recorded but not used in the math. |
| sku | text | Stock-keeping unit the row affects. |
| description | text | Plain name carried through to the output. |
| category | text | `raw_material`, `packaging_material`, or `finished_goods`. |
| txn_type | text | `opening`, `receipt`, or `issue`. |
| quantity | number | Greater than zero, in the SKU's stock unit. |
| unit | text | Stock unit. |
| value | number | Dollars added on an `opening` or `receipt`. Blank on an `issue`. |

Receipt values come from the procurement tool's landed costs; finished-goods
receipt values come from the batch tool's finished-unit line costs; issues are
materials drawn into production and finished goods shipped to customers.

## Validation rules
The file is rejected, with nothing written, if any row fails a check. Each
failure names the row and the problem:

- A required column is missing from the header.
- `txn_id` is blank or repeats an earlier one.
- `sku` or `unit` is blank.
- `category` is not one of the three allowed values.
- `txn_type` is not `opening`, `receipt`, or `issue`.
- `quantity` is non-numeric, or is zero or negative.
- An `opening` or `receipt` has a negative or missing `value`.

## Logic
1. Group the rows by SKU in the order each SKU first appears, keeping file order within a SKU.
2. Replay each SKU's transactions:
   - `opening` and `receipt` raise the quantity on hand and add their value to the dollar balance.
   - `issue` draws the balance down at the current weighted-average unit cost, the dollar balance divided by the quantity on hand. The unit cost re-averages on every receipt and holds steady on every issue.
   - If quantity on hand ever goes below zero, the SKU is marked with a `negative on-hand` integrity flag and processing continues, so the bad data surfaces instead of hiding.
3. Report each SKU's ending quantity, weighted-average unit cost, and inventory value, and total the value by category.

Money is held as `decimal.Decimal` and rounded half up to the cent. Weighted-average
unit cost is shown to four decimal places.

## Outputs
`perpetual_valuation.csv`, one row per SKU: `sku`, `description`, `category`,
`on_hand_qty`, `unit`, `wac_unit_cost`, `inventory_value`, `integrity_flag`. The
month-end close reads this file and reconciles it against the physical count.

## Edge cases
The sample data exercises each branch:

- **Opening balance plus receipts plus an issue** on the same SKU (RM-MALT).
- **A single-receipt finished good** drawn down by a sale (each FG SKU).
- **A weighted average that blends an opening and two receipts** (RM-MALT, opening at $1.2625 and two receipts).
- **A negative on-hand integrity flag** from an over-issue (RM-FININGS, 7 kg issued against 5 kg on hand), which the month-end close lists as an exception.
- The invalid sample carries a duplicate id, a bad category, an unknown transaction type, a negative quantity, a negative receipt value, and a receipt with no value, so the rejection path can be seen.

### Hand-checked example
RM-MALT (kilograms):

- Opening 500 kg valued at $631.25.
- Receipt 3,000 kg at $3,750.00 landed, then receipt 1,000 kg at $1,300.00 landed. Balance 4,500 kg, $5,681.25, unit cost $1.2625.
- Issue 830 kg to production at $1.2625 = $1,047.88. Ending balance 3,670 kg, $4,633.37.

Total inventory value across all eleven SKUs = **$17,240.79**: raw material
$8,167.77, packaging $7,997.18, and finished goods $1,075.84. This total is
checked by `test_valuation.py` here, and again by the month-end close, which
reconciles every line against the physical count and lists the RM-FININGS
negative as an exception.
