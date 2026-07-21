# Data dictionary

## expected/key_figures.csv

One row per key figure. Two columns.

| Column | Type | Meaning |
|---|---|---|
| `figure` | text | Key-figure name. Year-level figures carry the report year as a suffix, for example `margin_pct_2024`. |
| `value` | text | The figure's value, written exactly as the verification compares it. Percentages and ratios carry two decimals, dollar totals are whole numbers, direction flags are text. |

### Figure names

| Figure | Type | Meaning | Units |
|---|---|---|---|
| `margin_pct_<year>` | percent | Net income as a share of total income for that report year, times 100, rounded to two decimals | percent |
| `margin_dir_<year>` | flag | Direction of the rounded margin against the prior year: `up`, `down`, or `flat`; `n/a` for the first observed year | none |
| `equity_ratio_pct_<year>` | percent | Total equity as a share of total assets for that report year, times 100, rounded to two decimals | percent |
| `equity_dir_<year>` | flag | Direction of the rounded equity ratio against the prior year | none |
| `solvency_ratio_<year>` | ratio | Total assets over total liabilities for that report year, rounded to two decimals | multiple |
| `employees_per_coop_<year>` | ratio | Total employees over the number of reporting co-ops for that report year, rounded to two decimals | employees per co-op |
| `employees_dir_<year>` | flag | Direction of the rounded employees-per-co-op figure against the prior year | none |
| `total_income_all_years` | money | Sum of `total_income` across all observed report years | CAD, whole dollars |
| `total_expenses_all_years` | money | Sum of `total_expenses` across all observed report years | CAD, whole dollars |
| `total_net_income_all_years` | money | Sum of `net_income` across all observed report years | CAD, whole dollars |
| `overall_margin_pct` | percent | Total net income over total income across all observed years, times 100, rounded to two decimals | percent |
| `latest_year` | year | Most recent observed report year | none |
| `latest_margin_pct` | percent | Operating margin in the latest report year | percent |
| `latest_margin_dir` | flag | Margin direction in the latest report year | none |
| `latest_equity_ratio_pct` | percent | Equity ratio in the latest report year | percent |
| `latest_equity_dir` | flag | Equity ratio direction in the latest report year | none |
| `latest_solvency_ratio` | ratio | Solvency in the latest report year | multiple |
| `latest_employees_per_coop` | ratio | Employees per reporting co-op in the latest report year | employees per co-op |
| `latest_employees_dir` | flag | Employees-per-co-op direction in the latest report year | none |

## Data sheet (workbook)

Prepared rows from the snapshot, one per report year, sorted ascending. Values only, no formulas. Column names match the dataset's own, including its singular `total_liability`.

| Column | Type | Meaning | Units |
|---|---|---|---|
| `report_year` | integer | Calendar year the co-op reports cover | year |
| `co_ops_reporting` | integer | Co-operatives that filed their annual report | co-ops |
| `total_income` | integer | Combined income of the reporting co-ops | CAD, whole dollars |
| `total_expenses` | integer | Combined expenses of the reporting co-ops | CAD, whole dollars |
| `net_income` | integer | Combined net income as reported | CAD, whole dollars |
| `total_assets` | integer | Combined assets of the reporting co-ops | CAD, whole dollars |
| `total_liability` | integer | Combined liabilities of the reporting co-ops | CAD, whole dollars |
| `total_equity` | integer | Combined member equity of the reporting co-ops | CAD, whole dollars |
| `full_time_employees` | integer | Full-time employees across the reporting co-ops | persons |
| `part_time_employees` | integer | Part-time employees across the reporting co-ops | persons |
| `total_employees` | integer | Full-time plus part-time employees | persons |
| `total_members` | integer | Members across the reporting co-ops | persons |

## Model sheet (workbook)

Every figure below is a live formula; nothing is pasted.

| Block | Contents |
|---|---|
| Per-year table (rows 5 to 14) | Report year, income, expenses, and net income pulled from the Data sheet, then operating margin, equity ratio, solvency, and employees per reporting co-op as live divisions rounded to two decimals, each ratio followed by its year-over-year direction flag (`up`, `down`, `flat`, or `n/a` in the first year) |
| Sector totals (rows 17 to 20) | `SUM` of income, expenses, and net income over the Data sheet's whole-dollar columns, and the overall margin as the ratio of the two sums |
| Headline (rows 23 to 30) | Latest report year with its margin, equity ratio, solvency, and employees per reporting co-op, plus the three direction flags, all as references into the per-year table |
