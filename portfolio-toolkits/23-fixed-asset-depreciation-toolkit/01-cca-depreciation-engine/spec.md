# CCA depreciation engine

## Purpose
Takes a fixed-asset register and the opening undepreciated capital cost (UCC) for
each CRA class, then produces two schedules: straight-line book depreciation per
asset, and the Capital Cost Allowance (CCA) rollforward per class. A staff or
fixed-asset accountant runs it at year end to get both the book and the tax view
of the asset base from one source of truth.

## Inputs
Two CSV files.

`sample_assets.csv`, one row per asset:

| Column | Type | Meaning |
| --- | --- | --- |
| asset_id | text | Unique identifier for the asset |
| description | text | Plain description |
| cca_class | text | CRA CCA class: 1, 8, 10, 12, 50, 53, or 14.1 |
| capital_cost | decimal | Original capital cost |
| in_service_date | date (YYYY-MM-DD) | When the asset was placed in service |
| useful_life_years | integer > 0 | Book life for straight-line depreciation |
| salvage_value | decimal | Estimated residual value, 0 or more, not above cost |
| disposed | Y or N | Whether the asset was disposed in the year |
| disposal_proceeds | decimal | Proceeds on disposal, required when disposed is Y |
| prior_accum_book_dep | decimal | Book depreciation taken in prior years |

`opening_ucc.csv`, one row per class:

| Column | Type | Meaning |
| --- | --- | --- |
| cca_class | text | CRA CCA class |
| opening_ucc | decimal | UCC carried in from the prior year |

## Validation rules
- `cca_class` must be one of the known classes. Otherwise: unknown CCA class.
- `capital_cost` must be a number and cannot be negative.
- `salvage_value` must be a number, cannot be negative, and cannot exceed capital cost.
- `useful_life_years` must be a whole number greater than zero.
- `in_service_date` must be a real date in YYYY-MM-DD format.
- `disposed` must be Y or N.
- `disposal_proceeds` is required and cannot be negative when `disposed` is Y.
- `prior_accum_book_dep` cannot be negative and cannot exceed cost less salvage.
- Required fields cannot be blank. `disposal_proceeds` may be blank only when `disposed` is N.
- Opening UCC rows must name a known class and cannot be negative.

## Logic
Money is handled with `decimal.Decimal` and rounded half up to the cent.

Book depreciation, per asset:
1. Depreciable base = capital cost less salvage value.
2. Annual charge = base divided by useful life, rounded to the cent.
3. Current-year charge = the annual charge, capped so accumulated depreciation
   never passes the base. A fully depreciated asset takes zero.
4. A disposed asset takes no current-year charge and its accumulated balance
   holds at the prior-year figure.

CCA, per class pool:
1. Additions = capital cost of assets placed in service in the tax year.
2. Disposals = for each disposed asset, the lesser of proceeds and capital cost.
3. UCC before CCA = opening UCC + additions - disposals.
4. If UCC before CCA is negative, the shortfall is recapture, the pool resets to
   zero, and no CCA is taken.
5. If the pool is positive but no assets remain in the class, the remainder is a
   terminal loss, the pool goes to zero, and no CCA is taken.
6. Otherwise the half-year rule holds back half of net additions (additions less
   disposals, when positive) from the base, CCA = class rate times that base, and
   closing UCC = UCC before CCA less CCA.

The CRA rates used, for the 2026 tax year: class 1 at 4%, class 8 at 20%, class
10 at 30%, class 12 at 100%, class 50 at 55%, class 53 at 50%, class 14.1 at 5%.

## Outputs
`per_asset_schedule.csv`: asset_id, description, cca_class, capital_cost,
salvage_value, useful_life_years, in_service_date, disposed, annual_book_dep,
prior_accum_book_dep, current_book_dep, accum_book_dep, net_book_value.

`per_class_cca.csv`: cca_class, rate, opening_ucc, additions, disposals,
half_year_adjustment, cca_base, cca, recapture, terminal_loss, closing_ucc,
net_book_value, temporary_difference. The temporary difference is net book value
less closing UCC, the book-versus-tax timing gap the dashboard reads.

## Edge cases
The sample register is seeded so one run touches every branch:
- Clean asset held all year (FA-001, class 8 shelving).
- Half-year-rule addition placed in service this year (FA-002, class 8 forklift).
- Disposal with recapture (FA-003, class 10 van).
- Disposal with terminal loss (FA-004, class 50 server rack, the only asset in its class).
- Fully depreciated asset with a zero pool (FA-005, class 12 tools).
- `sample_assets_invalid.csv` carries an unknown class, a negative cost, a missing
  life, a malformed date, and a salvage above cost for the rejection path.

Hand-checked example, class 8, proven to the cent and matched by the SQL runner in
`../02-asset-register-rollforward`:

- Opening UCC 10,000.00, addition 5,000.00 (the forklift, in service this year),
  no disposals.
- Net additions 5,000.00, so the half-year adjustment is 2,500.00.
- CCA base = 10,000.00 + 5,000.00 - 2,500.00 = 12,500.00.
- CCA = 20% x 12,500.00 = 2,500.00.
- Closing UCC = 15,000.00 - 2,500.00 = 12,500.00.
- Net book value of the two class 8 assets = 1,600.00 + 4,100.00 = 5,700.00, so the
  temporary difference = 5,700.00 - 12,500.00 = -6,800.00.

The class 10 disposal produces recapture of 3,000.00 (4,000.00 opening less 7,000.00
proceeds capped at the 9,000.00 cost). The class 50 disposal produces a terminal loss
of 900.00 (1,200.00 opening less 300.00 proceeds, with no assets left in the class).
