# Contact Centre Workforce Visualizations

A personal project, one of several I build to model real-world job descriptions and turn them into
working business utilities. The goal is to practice applied problem-solving on the kind of work a
contact centre workforce-management analyst does, while strengthening my foundational software
development skills.

Two browser visualizations that connect into one workflow: plan the staffing, then monitor the day
against it. The Staffing Planner reads a call forecast, sizes agents per interval with the Erlang C
model, and exports a staffing plan. The Service-Level Dashboard reads that plan alongside the day's
actuals and shows how each interval performed, flagging the ones that fell short. Both are
deterministic and rule-based, with the rules written out in each tool's spec. The logic is written
in TypeScript and compiled to plain JavaScript, which is included, so each tool opens by
double-clicking its HTML file with no build step, no framework, and no server.

## The tools
1. **[Staffing Planner](staffing-planner/)** - reads a forecast CSV, computes required and rostered
   agents per interval with Erlang C, and exports `staffing-plan.csv`.
2. **[Service-Level Dashboard](service-level-dashboard/)** - reads the actuals CSV and the plan,
   charts service level against the target, and flags understaffed intervals.

The planner produces the plan the dashboard reads, so the two agree on the same intervals and the
same required-agent numbers.

## License
MIT, copyright Kevin Yu (github.com/exekyute).
