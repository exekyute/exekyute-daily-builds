# Building the Power BI dashboard

This walks through loading the exported CSVs in Power BI Desktop, modelling the
relationships, adding a few DAX measures, and building a small report. It assumes
no prior model. The files live in `../bi-exports/`.

Run `python engine/build_db.py` first so the CSVs exist and are current.

## 1. Load the data

1. Open Power BI Desktop and choose **Home > Get data > Text/CSV**.
2. Load these files one at a time, or use **Get data > Folder** and point it at
   `bi-exports` to bring them all in at once: `characters.csv`, `dim_races.csv`,
   `dim_nations.csv`, `dim_arcs.csv`, `dim_skills.csv`, `dim_factions.csv`,
   `bridge_character_skills.csv`, `bridge_character_factions.csv`.
3. In the preview, check that `ep_estimate` comes in as a whole number and the id
   columns as whole numbers. Click **Load**.

## 2. Model the relationships

Open the **Model** view and draw these relationships by dragging one key onto the
other. All of them are one-to-many from the dimension side to `characters` or the
bridge, with a single cross-filter direction unless noted.

| One side | Many side | Key |
| --- | --- | --- |
| dim_races[race_id] | characters[race_id] | race_id |
| dim_nations[nation_id] | characters[nation_id] | nation_id |
| dim_arcs[arc_id] | characters[debut_arc_id] | arc_id |
| characters[character_id] | bridge_character_skills[character_id] | character_id |
| dim_skills[skill_id] | bridge_character_skills[skill_id] | skill_id |
| characters[character_id] | bridge_character_factions[character_id] | character_id |
| dim_factions[faction_id] | bridge_character_factions[faction_id] | faction_id |

For the skill and faction views to slice correctly from the dimension side, set the
cross-filter direction on the two bridge relationships to **Both**.

As with Tableau, you can build most character charts straight from `characters.csv`
without any of this, since it already carries the race, nation, and arc labels. The
model matters for the skill and faction breakdowns.

## 3. DAX measures

Create these with **Modeling > New measure**. Put them on the `characters` table.

```DAX
Character Count = DISTINCTCOUNT ( characters[character_id] )

Characters with EP = CALCULATE ( [Character Count], NOT ISBLANK ( characters[ep_estimate] ) )

Total Existence Points = SUM ( characters[ep_estimate] )

Avg Existence Points = AVERAGE ( characters[ep_estimate] )

Max Existence Points = MAX ( characters[ep_estimate] )

Awakened Demon Lords =
CALCULATE ( [Character Count], characters[demon_lord_class] = "Awakened" )

Running Cast =
VAR current_arc = MAX ( dim_arcs[sequence_no] )
RETURN
    CALCULATE (
        [Character Count],
        FILTER ( ALL ( dim_arcs ), dim_arcs[sequence_no] <= current_arc )
    )
```

The `Running Cast` measure gives the cumulative number of characters introduced up
to and including each arc, for the story-growth chart.

## 4. Build the visuals

Each of these is one visual on the report canvas.

**Cast by race category.** Clustered bar chart. Axis: `characters[race_category]`.
Values: `Character Count`. Sort descending.

**Strongest characters by Existence Points.** Clustered bar chart. Axis:
`characters[name]`. Values: `characters[ep_estimate]` (or `Max Existence Points`).
Legend: `characters[threat_rank]`. Add a Top N filter on the visual: keep the top 15
by EP. Rimuru leads at 251 million, then Dagruel and Milim.

**Nation rosters and standing.** Clustered bar chart. Axis: `characters[nation]`.
Values: `Character Count`. Legend: `characters[relation_to_tempest]`. Sort
descending. Tempest dwarfs the rest.

**Skills by tier.** Clustered column chart using the skill bridge. Axis:
`bridge_character_skills[skill_type]`. Values: count of `bridge_character_skills`.

**Growing cast across the story.** Line chart. Axis: `dim_arcs[sequence_no]` (or the
arc name sorted by it). Values: `Running Cast`. This climbs arc by arc.

**Faction sizes.** Clustered bar chart using the faction bridge. Axis:
`dim_factions[name]`. Values: count of `bridge_character_factions`. Legend:
`dim_factions[aligned_with]`. Sort descending.

## 5. Add slicers and arrange

1. Add a **slicer** for `characters[relation_to_tempest]` and another for
   `dim_races[category]`. With the relationships in place, they filter every visual
   at once.
2. Arrange the six visuals on one page. A clean layout is the EP bar chart across the
   top, the nation and faction bars in the middle, and the running-cast line along the
   bottom, with the two slicers down one side.
3. Give the page a title such as "TenSura World Database".

## Sorting the arc axis

If the arc name axis sorts alphabetically, select the `dim_arcs` table, click the
`name` column, and use **Column tools > Sort by column > sequence_no** so the arcs
run in story order.

## Screenshots to capture

- The finished report page with the slicers and all visuals.
- The EP bar chart with Rimuru's bar and value in frame.
