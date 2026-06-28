# Cost Dashboard

## Purpose
Draws the period close on one page: inventory value by category, how the batch
cost builds, excise duty by ABV class, the month-end count variances, and the
SKU margin ranking. It reads the CSVs the rest of the pipeline produced and shows
them together, so a cost accountant or a manager can see the whole month at a
glance.

## Inputs
The five pipeline CSVs, loaded with the file picker or from the bundled sample:

- `perpetual_valuation.csv` (valuation tool): inventory value by SKU and category.
- `batch_costs.csv` (batch tool): the cost components per batch.
- `sku_margins.csv` (margin tool): revenue and margin by sales line.
- `excise_summary.csv` (excise tool): duty by ABV class.
- `physical_counts.csv`: the counted quantity per SKU, for the variance view.

Each file is routed by a column only it carries, so the order they are selected
does not matter. Files are read with the browser's FileReader and never sent
anywhere. A "Load sample data" button renders the bundled sample immediately.

## Validation rules
If a required dataset is missing after loading, the dashboard does not draw a
half-empty page. It shows a clear message naming which datasets are still needed.
A file whose header matches none of the five is named in the message rather than
silently ignored.

## Logic
- **Inventory valuation by category**: total the inventory value by category and show the grand total.
- **Batch cost waterfall**: sum ingredients, labour, overhead, and packaging across the batches, and show each as a step building to the total batch cost.
- **Excise duty by ABV class**: the duty and hectolitres for each class, with the total.
- **Month-end variances**: join the physical count to the book inventory, compute the quantity variance and its value at the weighted-average cost, and flag anything past the $50.00 tolerance or carrying an integrity flag. This mirrors the SQL close.
- **SKU margin ranking**: sort the sales lines by gross margin, highest first.

Money is carried in integer cents and only formatted for display with
`Intl.NumberFormat`, so the figures match the Python and SQL tools to the cent.

## Outputs
A rendered dashboard. Nothing is written to disk and nothing leaves the browser.

## Edge cases
The bundled sample exercises each branch:

- **A negative inventory line** (RM-FININGS), shown in the valuation and flagged in the variance view.
- **Two exceptions** in the variance table (RM-HOPS over tolerance, RM-FININGS integrity flag), highlighted.
- **An overage and a shortage** among the counts.
- **Both ABV classes** in the excise view.
- Loading a file the dashboard does not recognise, or a missing dataset, shows the error message rather than a broken page.

### Hand-checked example
Loaded with the bundled sample, the dashboard shows total inventory
**$17,240.79**, a batch cost waterfall summing to **$6,355.99**, total excise
**$149.17**, **2** count exceptions, and the radler can as the top margin line.
These match the valuation tool, the batch tool, the excise tool, and the SQL
close. The pure logic is checked by `tests.html`, which runs 16 assertions
against the same sample and prints a green pass count.
