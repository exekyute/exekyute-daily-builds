# SaaS Revenue and Retention Visualizations

A personal project, one of several I build to model real-world job descriptions and turn them into
working business utilities. The goal is to practice applied problem-solving on the kind of work a
SaaS revenue or subscription analyst does, while strengthening my foundational software
development skills.

The repo holds three connected visualizations that read one book of recurring-revenue data from
three angles. The MRR Movement Waterfall rolls each month forward and exports a movement table;
the Cohort Retention Heatmap reads the same ledger and tracks each signup cohort over time; and
the Churn and Renewal Dashboard reads the waterfall's exported movement table to report churn and
retention, alongside a renewals file for the contracts coming up. The tools are deterministic and
rule-based, with the rules written out in each spec. The logic is written in TypeScript and
compiled to plain JavaScript that the pages load directly, so each tool opens by double-clicking
its HTML file, with no framework, no build step, and no server. Everything runs on your machine.

## The tools
1. **MRR Movement Waterfall** - rolls a monthly recurring-revenue ledger from opening to closing,
   splitting the change into new, expansion, contraction, and churned revenue, and exports the
   movement table the dashboard reads.
2. **Cohort Retention Heatmap** - groups customers by signup month and shows how much of each
   cohort stays over the months that follow, as revenue retained or customers retained.
3. **Churn and Renewal Dashboard** - reads the movement table to report the MRR churn rate, gross
   revenue retention, and net revenue retention, and lists upcoming renewals from a renewals file.

The first tool produces a CSV the third tool reads, and the two agree to the cent: the waterfall's
April closing of $2,750.00 is the same figure the dashboard rebuilds from the movement components,
giving a 2.00% churn rate, 96.00% gross revenue retention, and 100.00% net revenue retention. The
worked example is written out in each tool's spec. Money is in Canadian dollars.

## License
MIT, copyright Kevin Yu (github.com/exekyute).
