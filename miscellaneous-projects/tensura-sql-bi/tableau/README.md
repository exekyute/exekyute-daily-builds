# Building the Tableau dashboard

This walks through connecting the exported CSVs in Tableau Public or Tableau
Desktop and building a small dashboard from them. It assumes no prior model, so
every step is spelled out. The files live in `../bi-exports/`.

Run `python engine/build_db.py` first so the CSVs exist and are current.

## 1. Connect the data

1. Open Tableau and choose **Connect > To a File > Text file**.
2. Pick `bi-exports/characters.csv`. Tableau opens the Data Source tab with that
   table on the canvas.
3. Drag in the other files you want to relate: `dim_races.csv`, `dim_nations.csv`,
   `dim_arcs.csv`, `dim_skills.csv`, `dim_factions.csv`, `bridge_character_skills.csv`,
   and `bridge_character_factions.csv`.

## 2. Set the relationships

Tableau's relationships (the noodle lines on the canvas) keep each table at its own
grain, which is what you want here. Drag a table onto `characters` and match the
keys:

| From | Field | To | Field |
| --- | --- | --- | --- |
| characters | race_id | dim_races | race_id |
| characters | nation_id | dim_nations | nation_id |
| characters | debut_arc_id | dim_arcs | arc_id |
| characters | character_id | bridge_character_skills | character_id |
| bridge_character_skills | skill_id | dim_skills | skill_id |
| characters | character_id | bridge_character_factions | character_id |
| bridge_character_factions | faction_id | dim_factions | faction_id |

For simple character charts you can skip all of this and use `characters.csv` on
its own, since it already carries the race, nation, and arc labels. The
relationships matter for the skill and faction breakdowns, which live in the
bridge tables.

## 3. Calculated fields

Create these from **Analysis > Create Calculated Field**. They make the charts
read better.

- **EP (millions)**: `[Ep Estimate] / 1000000`
- **Has EP**: `IF ISNULL([Ep Estimate]) THEN 'No figure' ELSE 'Has figure' END`
- **Awakened**: `IF [Demon Lord Class] = 'Awakened' THEN 'Awakened' ELSE 'Other' END`
- **Threat Rank (sorted)**: a copy of `Threat Rank` you sort manually so the axis
  runs weakest to strongest. Right-click the pill on the shelf, choose **Sort >
  Manual**, and order it: F, E, D, C, B, A, A+, Special A, S, Special S.

## 4. Build the sheets

Each of these is one worksheet. Rename the sheet as you go so the dashboard is easy
to assemble.

**Sheet 1: Cast by race category.**
Columns: `Race Category`. Rows: `CNTD(Character Id)` (or `Number of Records`).
Sort descending. This is a clean bar chart of how the world's cast splits across
Demon, Dragon, Human, Humanoid, and the rest.

**Sheet 2: Strongest characters by Existence Points.**
Filter `Ep Estimate` to Non-Null values. Rows: `Name`. Columns: `EP (millions)`.
Sort descending. Drop `Threat Rank` on Color. This is the marquee chart: Rimuru
on top, then Dagruel, Milim, Veldora, and the other apex beings.

**Sheet 3: Nation rosters and standing.**
Columns: `Nation`. Rows: `CNTD(Character Id)`. Drop `Relation To Tempest` on Color.
Sort descending. Shows Tempest towering over the other nations, colored by whether
each nation is an ally, a rival, or an enemy.

**Sheet 4: Skills by tier and the busiest characters.**
Using the skill bridge, put `Skill Type` on Columns and `COUNT` of
`bridge_character_skills` on Rows for the tier breakdown. For a second view, put
`Name` on Rows and the same count on Columns, sort descending, and filter to the
top ten to show who carries the most skills (Rimuru runs away with it).

**Sheet 5: Growing cast across the story.**
Columns: `Debut Arc No` (continuous). Rows: a running total of `CNTD(Character Id)`.
Add a quick table calculation: right-click the measure, **Quick Table Calculation >
Running Total**. Use `Debut Arc` for the tooltip. This is an area or line chart of
the cast growing arc by arc.

**Sheet 6: Faction sizes.**
Using the faction bridge, Columns: `COUNT`. Rows: `Faction`. Color by
`Aligned With`. Sort descending. Shows the Tempest leadership and the demon lord
councils as the largest groups.

## 5. Assemble the dashboard

1. Click **New Dashboard**.
2. Drag Sheets 2, 3, 5, and 6 onto the canvas in a two-by-two grid. These four tell
   the clearest story: who is strongest, who stands where, how the cast grows, and
   how the groups compare.
3. Add a title such as "TenSura World Database".
4. Add `Relation To Tempest` or `Race Category` as a dashboard filter if you want
   the panels to cross-filter.

## Screenshots to capture

- The finished dashboard with all four panels visible.
- The EP bar chart on its own with Rimuru's bar and value in frame.
