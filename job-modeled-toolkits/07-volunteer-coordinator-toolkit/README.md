# Volunteer Coordinator Toolkit

A personal project, one of several I build to model real-world job descriptions
and turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a volunteer coordinator does, while
strengthening my foundational software development skills.

The repository holds three small browser tools written in plain HTML, CSS, and
vanilla JavaScript. Each one is self-contained, rule-based, and built around clean
business logic, careful input validation, and data integrity. There is no
framework, no build step, and no server: every tool opens by double-clicking its
HTML file, and any file you load is read in the browser with the `FileReader` API
and stays on your machine. Durations are tracked in whole minutes and dates and
times are written explicitly, dates as `YYYY-MM-DD` and times on a 24-hour clock,
so output is never ambiguous and totals do not drift.

## The tools

1. **[Onboarding Eligibility Validator](01-onboarding-eligibility-validator/)**
   checks each volunteer's completed requirements and clears only those who are of
   age and have a passed and unexpired background check, every required training,
   and a signed unexpired waiver. It produces the cleared roster the planner uses.
2. **[Shift Coverage Planner](02-shift-coverage-planner/)** takes the shifts that
   need filling and the volunteers signed up for them, counts only cleared
   volunteers toward coverage, and flags understaffed and overstaffed shifts and
   any volunteer double-booked across overlapping shifts.
3. **[Volunteer Hours Dashboard](03-volunteer-hours-dashboard/)** loads a CSV of
   logged hours with the FileReader API and shows totals per volunteer, milestone
   flags, and anomalies such as overlapping or excessive entries.

## How they connect

The Onboarding Eligibility Validator is the gate the scheduling depends on. It
emits a cleared roster, `cleared_roster.json`, and the Shift Coverage Planner ships
that same file, byte for byte. Jordan Lee (V-105) is blocked at onboarding for a
missing background check, so he is `cleared: false` in that roster. When he is the
only volunteer signed up for a shift, the planner rejects his assignment and leaves
the shift understaffed. That worked example is documented in both tools' `spec.md`.
The Volunteer Hours Dashboard covers the separate job of tracking hours and
recognizing milestones, using the same cast of volunteers.

## Running the tools

Open the tool's `index.html` in a web browser by double-clicking it. Nothing to
install. Each tool also has a `tests.html` that runs its logic against hand-worked
numbers and prints PASS or FAIL on the page, so the checks run with no build
tooling.

Each tool folder has its own README with worked examples and screenshots, and a
`spec.md` describing purpose, inputs, validation, logic, outputs, and edge cases.

## Repository layout

```
volunteer-coordinator-toolkit/
  LICENSE
  README.md
  01-onboarding-eligibility-validator/
  02-shift-coverage-planner/
  03-volunteer-hours-dashboard/
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
