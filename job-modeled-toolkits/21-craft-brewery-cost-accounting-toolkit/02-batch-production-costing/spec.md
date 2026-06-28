# Batch Production Costing

## Purpose
Rolls raw materials, packaging, labour, and overhead into the cost of each brew
batch, accounts for yield loss between wort and packaged beer, and works out the
cost of every finished unit (a can or a keg). A cost accountant runs it after the
landed-cost tool to value production for the period.

## Inputs
The landed-cost file from the procurement tool, plus three CSVs for the period:

`landed_costs.csv` (from tool 01): used to derive a weighted-average landed cost
per material SKU. The period cost of a SKU is its total landed value divided by
its total quantity received, at full precision.

`batches.csv`, one row per batch:

| Column | Type | Notes |
| --- | --- | --- |
| batch_id | text | Unique. |
| beer | text | Beer name. |
| product_line | text | Carried through for margin reporting. |
| abv_pct | number | Alcohol by volume, recorded for reference. |
| abv_class | text | `over_2_5`, `over_1_2_to_2_5`, or `not_over_1_2`, for excise. |
| brewed_litres | number | Wort volume at the start of the batch. |
| finished_litres | number | Packaged volume after yield loss. Cannot exceed brewed. |
| labour_cost | number | Direct labour charged to the batch. |
| overhead_cost | number | Overhead applied to the batch. |

`batch_ingredients.csv`, the bill of materials: `batch_id`, `material_sku`,
`quantity`, `unit`. Each SKU must have a landed cost.

`packaging_runs.csv`, how the finished beer is packaged: `batch_id`, `fg_sku`,
`description`, `container_sku`, `label_sku` (blank for kegs), `units`,
`litres_per_unit`.

## Validation rules
The run is rejected, with nothing written, if any check fails. Each failure names
the file, the row, and the problem:

- A required column is missing from any of the three files.
- `batch_id` is blank or repeats another.
- `abv_class` is not one of the three allowed values.
- `brewed_litres` or `finished_litres` is non-numeric or not positive.
- `finished_litres` exceeds `brewed_litres` (loss cannot be negative).
- `labour_cost` or `overhead_cost` is non-numeric or negative.
- An ingredient or packaging row points at a `batch_id` not in the register.
- A `material_sku`, `container_sku`, or `label_sku` has no landed cost.
- An ingredient `quantity` is non-numeric or not positive.
- `units` is not a whole number greater than zero, or `litres_per_unit` is not positive.

## Logic
1. Derive the weighted-average landed cost per material SKU from `landed_costs.csv`.
2. For each batch, cost the ingredient lines at that weighted-average cost, quantizing each line to the cent, and sum them. Add labour and overhead to get the brew cost (the work-in-process cost of the batch).
3. Spread the brew cost across the batch's packaging runs in proportion to packaged litres, using the largest-remainder method so the allocated cents sum back to the brew cost exactly. Yield loss is absorbed here: the brew cost is divided only over the beer that survives to packaging, so the lost litres raise the cost of the good litres.
4. Each packaging run adds the cost of its own materials: the container plus, for cans, the label, times the number of units.
5. A finished-unit line cost is its share of the beer cost plus its packaging materials. The unit cost is the line cost divided by the units. The finished-unit line costs sum back to the total batch cost exactly.
6. If a batch's packaged litres do not equal its finished litres, the batch is flagged so the mismatch is visible rather than hidden.

Money is held as `decimal.Decimal` and rounded half up to the cent. Cost per
finished litre is carried to six places for the allocation; unit cost is shown to
four places.

## Outputs
`batch_costs.csv`, one row per batch: `batch_id`, `beer`, `product_line`,
`abv_class`, `brewed_litres`, `finished_litres`, `yield_pct`, `ingredient_cost`,
`labour_cost`, `overhead_cost`, `brew_cost`, `packaging_material_cost`,
`total_batch_cost`, `cost_per_finished_litre`, `volume_flag`.

`finished_unit_costs.csv`, one row per packaging run: `fg_sku`, `description`,
`product_line`, `abv_class`, `batch_id`, `container_sku`, `units`,
`packaged_litres`, `beer_cost`, `packaging_material_cost`, `line_cost`,
`unit_cost`. The excise tool reads the packaged litres by ABV class, and the
margin and valuation tools read the unit costs.

## Edge cases
The sample data exercises each branch:

- **Two packaging runs from one batch** (cans and kegs), so the brew cost is split by volume (BATCH-L01).
- **A single-run batch** where one run takes the whole brew cost (BATCH-R01, Radler in cans only).
- **A second ABV class** for excise downstream (BATCH-R01 is `over_1_2_to_2_5`, the others `over_2_5`).
- **Yield loss** on every batch, raising the cost per finished litre above the per-brewed-litre figure.
- The invalid sample set carries negative loss, a bad ABV class, a duplicate batch, an orphan batch reference, an unknown material, a zero quantity, fractional units, an unknown container, and a zero `litres_per_unit`, so the rejection path can be seen.

### Hand-checked example
BATCH-L01, Harbourview Lager:

- Malt 380 kg at the $1.2625 weighted-average = $479.75. Hops 8 kg at $19.68 = $157.44. Ingredient cost $637.19.
- Labour $600.00 plus overhead $400.00, so brew cost = $1,637.19.
- Packaged into 3,000 cans (1,065.000 L) and 15 kegs (750 L), 1,815 L in total, matching the finished litres.
- Beer cost split by volume: cans get 1,637.19 times 1,065 / 1,815 = $960.67; kegs get 1,637.19 times 750 / 1,815 = $676.52. The two sum to $1,637.19.
- Can packaging materials: 3,000 times ($0.09375 can + $0.0203395 label) = $342.27. Keg packaging: 15 times $45.7642 = $686.46.
- Can line cost $960.67 + $342.27 = $1,302.94; keg line cost $676.52 + $686.46 = $1,362.98. Total batch cost = **$2,665.92**, equal to the two line costs.

Total cost across the three batches = **$6,355.99**. This total is checked by
`test_batch.py`, and the finished-unit values flow into the excise, valuation,
and margin tools.
