# Fixed-asset dashboard

## Purpose
Reads the per-class CCA file the engine writes and lays it out for review:
Capital Cost Allowance by class, the book net book value against the tax UCC, and
the full class rollforward with recapture and terminal-loss flags. A fixed-asset
accountant or a reviewer opens it to see the year-end position at a glance.

## Inputs
A `per_class_cca.csv` file, the output of the engine in
`../01-cca-depreciation-engine`, chosen with the file picker. The page also ships
with the sample embedded so it shows something on first open. Required columns:
cca_class, opening_ucc, additions, disposals, half_year_adjustment, cca,
recapture, terminal_loss, closing_ucc, net_book_value, temporary_difference.

## Validation rules
- The file must contain every required column. A missing column is reported in red.
- Every money field must be a number. A non-numeric value names the class and
  column in red.
- A file with no class rows is reported.
Files are read with the FileReader API and never leave the browser.

## Logic
The pure logic in `src/dashboard.js` parses the CSV, converts every money field to
integer cents, and computes the totals and the bar-scaling maximum. Cents are
formatted for display with `Intl.NumberFormat` in Canadian dollars, so the figures
match the engine and the SQL rollforward to the cent. The page checks the pool
identity for each class (a class with recapture or a terminal loss closes at zero,
otherwise closing = opening + additions - disposals - CCA) and notes whether it
holds for every class.

## Outputs
On the page: four summary cards (total CCA, recapture, terminal loss, closing UCC),
a Capital Cost Allowance bar chart by class, a book-versus-tax bar comparison of net
book value against closing UCC, and the rollforward table with a recapture or
terminal-loss tag where one applies.

## Edge cases
The embedded sample carries a clean half-year class (8), a recapture class (10), a
terminal-loss class (50), and a zero pool (12), so every flag and the timing
difference are visible on first open. `sample_per_class_cca_bad.csv` is missing the
temporary_difference column for the rejection path.

Hand-checked example, class 8, matching the engine and the SQL runner: CCA
2,500.00, closing UCC 12,500.00, net book value 5,700.00, and a temporary
difference of -6,800.00. The class 10 recapture is 3,000.00 and the class 50
terminal loss is 900.00.
