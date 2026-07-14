# exekyute-daily-builds

A running collection of the small projects I build. Four kinds live here: job-modeled toolkits, where I turn a real job description into working software; Nova Scotia open-data analyses, where the logic lives in plain SQL; Halifax open-data builds, which put **Tableau** and **Power BI** dashboards on top of that same SQL; and miscellaneous projects, the smaller things I make to learn something or just to tinker.

Each project is self-contained in its own folder with its own README, so you can open any one on its own.

> **Note:** On June 25, 2026, I used Claude Code to consolidate my separate daily-build repositories into a single source. Folding them together cuts down on repo clutter and makes the whole collection easier to browse, track, and manage from one place. The "Last Updated" column shows when each project was last worked on. For projects folded in during the merge, that is their date beforehand; anything I add or update later carries its own date.

## Halifax Open Data

DuckDB SQL analyses built on real datasets from the Halifax Regional Municipality's open data hub. The ground rules match the Nova Scotia series below: a checked-in snapshot of the source data, a golden copy of the expected output, and SQL that reproduces it exactly. On top of that, each build ships a published **Tableau** dashboard and a committed **Power BI** report. Both read the same frozen CSV the SQL exports, so the two tools show identical figures to the cent.

<table>
<tr><th>Project</th><th>What it does</th><th>Last Updated</th></tr>
<tr><td><a href="hrm-open-data/02-collision-safety-map">02 Traffic Collision Safety Map</a></td><td>Maps where and when 46,285 Halifax traffic collisions cluster and what share involve pedestrians, cyclists, or impaired and distracted driving: a point density map and month-by-hour calendar heatmap in <strong>Tableau</strong>, factor-share measures with a what-if slicer in <strong>Power BI</strong>.</td><td>07/14/2026</td></tr>
<tr><td><a href="hrm-open-data/01-building-permit-pulse">01 Building Permit Pulse</a></td><td>Tracks permit activity and declared construction value across 18,316 Halifax building permits and follows where net new housing units land: a permit point map in <strong>Tableau</strong>, a value decomposition tree in <strong>Power BI</strong>.</td><td>07/13/2026</td></tr>
</table>

## Nova Scotia Open Data

Small DuckDB SQL analyses built on real datasets from the Nova Scotia Open Data portal, plus one formula-driven Excel model. Each build keeps a checked-in snapshot of its source data and a golden copy of the expected output, so the numbers reproduce exactly every time the build runs.

| Project | What it does | Last Updated |
|---|---|---|
| [10 Highway Capital-Plan Tracker](ns-open-data-sql/10-highway-capital-plan-tracker) | Pivots 393 planned road and bridge projects by county, fiscal year, and type in a formula-driven Excel workbook, with Pictou County leading and the Gravel Road Program the largest type. | 07/14/2026 |
| [09 Impaired-Driving Toxicology Trend](ns-open-data-sql/09-impaired-driving-toxicology-trend) | Groups driver deaths by toxicology result each year, tracks the share testing positive, and totals deaths by month, 2015 to 2024. | 07/13/2026 |
| [08 Procurement Spend Pareto](ns-open-data-sql/08-procurement-spend-pareto) | Sums awarded tender dollars by vendor (merging name variants) and traces an 80/20 curve of how few vendors reach 80 percent of spend. | 07/12/2026 |
| [07 Municipal Surplus League Table](ns-open-data-sql/07-municipal-surplus-league-table) | Computes each municipality's operating surplus by fiscal year and ranks the largest surpluses and deficits. | 07/11/2026 |
| [06 Liquor-License Density](ns-open-data-sql/06-liquor-license-density) | Counts permanent liquor licenses per community, ranks communities by total, and flags each one's dominant license type. | 07/10/2026 |
| [05 Busiest-Corridor AADT Ranking](ns-open-data-sql/05-busiest-corridor-aadt-ranking) | Ranks highway segments by average daily traffic, tracks each one's year-over-year growth, and flags those near two-lane capacity. | 07/09/2026 |
| [04 Hatchery Stocking Summary](ns-open-data-sql/04-hatchery-stocking-summary) | Sums hatchery fish releases by water, county, and species, and tracks the trend from 1976 to 2025. | 07/08/2026 |
| [03 Small-Business Grant Audit](ns-open-data-sql/03-small-business-grant-audit) | Counts recipients of two 2020 pandemic grants by business type and ranks which types got the most. | 07/07/2026 |
| [02 Farm Commodity-Mix Shift](ns-open-data-sql/02-farm-commodity-mix-shift) | Tracks the commodity mix of registered farms and ranks which gained or lost the most share, 2015-2016 to 2024-2025. | 07/06/2026 |
| [01 MVA Conviction Trend](ns-open-data-sql/01-mva-conviction-trend-by-statute) | Ranks two Motor Vehicle Act offences by yearly convictions and tracks which is rising or falling, 2011 to 2024. | 07/05/2026 |

## Miscellaneous Projects

Smaller builds, made to learn something or for fun.

<table>
<tr><th>Project</th><th>What it does</th><th>Last Updated</th></tr>
<tr><td><a href="miscellaneous-projects/bibliotheca-dantalian">Bibliotheca Dantalian</a></td><td>Zero-dependency static wiki engine with scoped spoiler blocks, wikilinks, and search, demoed on a wiki for a fictional anime.</td><td rowspan="2">07/12/2026</td></tr>
<tr><td><a href="miscellaneous-projects/save-point">Save Point</a></td><td>Astro guide and blog template for game guide sites: persistent checklists, sortable tables, galleries, and three themes.</td></tr>
<tr><td><a href="miscellaneous-projects/kev-wing-wah">Kev Wing Wah</a></td><td>Restaurant website template for a fictional takeout spot, with a searchable 120-dish menu.</td><td>07/03/2026</td></tr>
<tr><td><a href="miscellaneous-projects/ff7-materia-graph">FF7 Materia Graph</a></td><td>Knowledge graph of Final Fantasy VII materia, with a Python/SQLite command-line tool and a browser explorer.</td><td>06/27/2026</td></tr>
<tr><td><a href="miscellaneous-projects/knicks-spurs-matchup-projector">Knicks vs Spurs Matchup Projector</a></td><td>Single web page that projects the next Knicks vs Spurs game.</td><td>06/03/2026</td></tr>
<tr><td><a href="miscellaneous-projects/contact-list-cleaner">Contact List Cleaner</a></td><td>Command-line tool that tidies a messy contact list.</td><td>06/02/2026</td></tr>
<tr><td><a href="miscellaneous-projects/insertion-order-renamer">Insertion Order Renamer</a></td><td>Command-line tool that normalizes messy IO file names.</td><td>06/01/2026</td></tr>
<tr><td><a href="miscellaneous-projects/crossword-generator">Crossword Generator</a></td><td>Browser crossword generator that ships as one HTML file.</td><td>05/31/2026</td></tr>
<tr><td><a href="miscellaneous-projects/table-for-one">Table for One</a></td><td>A concept food blog written from the eating side of the table.</td><td>05/30/2026</td></tr>
<tr><td><a href="miscellaneous-projects/io-pdf-builder">Insertion Order PDF Builder</a></td><td>Browser form that builds a one-page insertion order PDF, with live preview and DocuSign anchor tags.</td><td rowspan="2">05/29/2026</td></tr>
<tr><td><a href="miscellaneous-projects/invoice-parsimus">InvoiceParsimus</a></td><td>Browser invoice parser and financial dashboard powered by Gemini.</td></tr>
<tr><td><a href="miscellaneous-projects/beginner-blog-api">Beginner Blog API</a></td><td>A first real backend: HTTP, auth, and a relational database.</td><td rowspan="2">05/28/2026</td></tr>
<tr><td><a href="miscellaneous-projects/steam-achievements-scraper">Steam Global Achievements Downloader</a></td><td>Firefox userscript that downloads a Steam game's achievement names, icons, and descriptions.</td></tr>
<tr><td><a href="miscellaneous-projects/finlit-tools-ca">Canadian FinLit Tools</a></td><td>Seven browser calculators for Canadian benefit and tax rules.</td><td>05/25/2026</td></tr>
</table>

<details>
<summary><h2>Job-Modeled Toolkits (1-30)</h2></summary>

Business utilities modeled on real job descriptions. Most are no-backend tools: Python command-line scripts, SQLite analytics, Excel VBA, or browser dashboards.

| Project | What it does | Last Updated |
|---|---|---|
| [30 Grant Drawdown and Compliance](job-modeled-toolkits/30-grant-compliance-toolkit) | Allowable-cost drawdown engine with run-rate projection and report deadlines, and a browser timeline against the award. | 07/04/2026 |
| [29 Expense and T&E Audit](job-modeled-toolkits/29-expense-audit-toolkit) | Policy-audit engine for mileage, caps, receipts, and duplicates, and a browser review queue with approve/reject. | 07/03/2026 |
| [28 IT Cost Allocation and Showback](job-modeled-toolkits/28-it-cost-allocation-toolkit) | Driver-based shared-cost allocation engine and an Excel chargeback workbook with live formulas. | 07/02/2026 |
| [27 Vendor SOW Earned-Value Tracker](job-modeled-toolkits/27-vendor-sow-tracker-toolkit) | Earned-value SOW engine and a browser burn-down timeline against budget. | 07/01/2026 |
| [26 Subscription and License Manager](job-modeled-toolkits/26-subscription-license-toolkit) | Subscription cost and seat-waste ledger, and an editable browser license manager with renewals. | 06/30/2026 |
| [25 Construction WIP and Job-Cost](job-modeled-toolkits/25-construction-wip-job-cost-toolkit) | Cost-to-cost WIP engine, an Excel workbook with live formulas, and a sort macro. | 06/29/2026 |
| [24 AI Operations](job-modeled-toolkits/24-ai-operations-toolkit) | LLM cost engine, model scorecard, and an AI ops dashboard. | 06/28/2026 |
| [21 Craft Brewery Cost Accounting](job-modeled-toolkits/21-craft-brewery-cost-accounting-toolkit) | Landed cost, batch costing, valuation, CRA excise, SKU margins, a SQL close, and a dashboard. | 06/27/2026 |
| [22 Municipal 311 SQL Analytics](job-modeled-toolkits/22-municipal-311-sql-analytics) | SQL intake, backlog flow, SLA aging, and operations dashboard. | 06/26/2026 |
| [23 Fixed-Asset Depreciation](job-modeled-toolkits/23-fixed-asset-depreciation-toolkit) | Canadian CRA CCA engine, rollforward, and dashboard. | 06/24/2026 |
| [18 Procurement Spend](job-modeled-toolkits/18-procurement-spend-visualizations) | Spend dashboard, supplier Pareto, and PO/invoice compliance. | 06/23/2026 |
| [20 Property and Casualty Claims](job-modeled-toolkits/20-property-casualty-claims-visualizations) | Claims aging funnel, loss ratio, and reserve triangle. | 06/23/2026 |
| [15 Membership Services](job-modeled-toolkits/15-membership-services-toolkit) | Dues and HST reporting, worklist, and dashboard. | 06/22/2026 |
| [17 Treasury Cash Management](job-modeled-toolkits/17-treasury-cash-management-visualizations) | Cash position, maturity ladder, and 13-week forecast. | 06/21/2026 |
| [14 Brewery Inventory Costing](job-modeled-toolkits/14-brewery-inventory-costing-toolkit) | Weighted-average costing and CRA excise engine. | 06/20/2026 |
| [19 SaaS Revenue and Retention](job-modeled-toolkits/19-saas-revenue-retention-visualizations) | MRR waterfall, cohort heatmap, and churn dashboard. | 06/19/2026 |
| [16 Contact Centre WFM](job-modeled-toolkits/16-contact-center-wfm-visualizations) | Erlang C planner and service-level dashboard. | 06/17/2026 |
| [10 Rent Roll](job-modeled-toolkits/10-rent-roll-toolkit) | Rent roll modeling tools. | 06/16/2026 |
| [12 Loan Servicing](job-modeled-toolkits/12-loan-servicing-toolkit) | Loan servicing and amortization tools. | 06/15/2026 |
| [01 Pricing and Profitability](job-modeled-toolkits/01-pricing-profitability-toolkit) | Margin and pricing models for profitability work. | 06/14/2026 |
| [06 Sales Compensation](job-modeled-toolkits/06-sales-compensation-toolkit) | Commission and quota calculator with a validator. | 06/14/2026 |
| [07 Volunteer Coordinator](job-modeled-toolkits/07-volunteer-coordinator-toolkit) | Volunteer scheduling and coordination tools. | 06/14/2026 |
| [09 Payroll Operations](job-modeled-toolkits/09-payroll-ops-toolkit) | Canadian CPP/EI net-pay calculator and dashboard. | 06/14/2026 |
| [11 AR Collections](job-modeled-toolkits/11-ar-collections-toolkit) | Python aging engine and collections dashboard. | 06/14/2026 |
| [13 Freight Allocation](job-modeled-toolkits/13-freight-allocation-toolkit) | Landed-cost allocation for inbound logistics. | 06/12/2026 |
| [08 Fund Administration](job-modeled-toolkits/08-fund-administration-toolkit) | Fund accounting and NAV tools. | 06/11/2026 |
| [04 Global Project Coordination](job-modeled-toolkits/04-global-project-coordination-toolkit) | Cross-region project coordination tools. | 06/09/2026 |
| [03 Site Compliance](job-modeled-toolkits/03-site-compliance-toolkit) | Tracking tools for site compliance. | 06/06/2026 |
| [02 Budget and Forecast](job-modeled-toolkits/02-budget-forecast-toolkit) | Budgeting and forecasting calculators. | 06/05/2026 |
| [05 Pension Administration](job-modeled-toolkits/05-pension-admin-toolkit) | Pension administration calculators. | 06/05/2026 |

</details>

## License

MIT. See [LICENSE](LICENSE).

Kevin Yu ([github.com/exekyute](https://github.com/exekyute))
