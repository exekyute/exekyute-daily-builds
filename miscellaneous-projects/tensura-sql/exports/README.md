# CSV exports and data dictionary

These CSVs are written by `engine/build_db.py` from the same SQLite database the
SQL queries run against, one flat table per file. Each one has a header row and
is UTF-8 encoded.

The model is a small star. `characters.csv` is the centre. The `dim_` files are
the dimensions it points at. The `bridge_` files carry the many-to-many links
(skills and factions), and the remaining files are detail tables for a slice of
characters.

`characters.csv` already carries readable label columns (race, nation, debut arc)
next to the id keys, so simple charts work from that one file without building any
relationships. Reach for the dimension and bridge files when you want slicers, a
proper model, or the skill and faction breakdowns.

## Keys and relationships

```
dim_races (race_id) ----------< characters (race_id)
dim_nations (nation_id) ------< characters (nation_id)
dim_arcs (arc_id) ------------< characters (debut_arc_id)

characters (character_id) ----< bridge_character_skills (character_id) >---- dim_skills (skill_id)
characters (character_id) ----< bridge_character_factions (character_id) >-- dim_factions (faction_id)
characters (character_id) ----< fact_evolutions (character_id)
characters (character_id) ---- demon_lords (character_id)      one-to-one, only demon lords
characters (character_id) ---- true_dragons (character_id)     one-to-one, only the four dragons
```

`dim_nations.ruler` is the name of the nation's ruler. It matches a value in
`characters.name` where that ruler is one of the modelled characters, and is blank
otherwise.

## Files

### characters.csv
One row per character (59 rows). The central table.

| column | meaning |
| --- | --- |
| character_id | primary key |
| name | character name |
| epithet | alias or title, may be blank |
| race_id, race, race_category, race_tier | race key and labels (category such as Demon or Dragon; tier is Base or Evolved) |
| nation_id, nation, relation_to_tempest | home nation key and labels; relation is Self, Ally, Rival, Enemy, Former Enemy, or Neutral |
| debut_arc_id, debut_arc, debut_arc_no | the arc the character first appears in, and its reading-order number |
| gender | Male, Female, or None |
| role_title | in-world role |
| alignment | Tempest, Ally, Antagonist, or Neutral |
| status | Alive, Deceased, Sealed, Revived, or Unknown |
| threat_rank | canon danger class: F, E, D, C, B, A, A+, Special A, S, Special S |
| demon_lord_class | None, Self-Proclaimed, or Awakened |
| ep_estimate | Existence Points, a wiki-cited figure; blank where none is published |
| is_demon_lord | 1 if the character has a demon_lords row |
| demon_lord_roster | Ten Great Demon Lords, Octagram, or Former, when a demon lord |
| is_true_dragon | 1 if one of the four True Dragons |
| skill_count | number of skills the character holds |
| evolution_steps | number of recorded evolution steps |

### dim_races.csv
One row per race (38). Columns: race_id, name, category, tier.

### dim_nations.csv
One row per nation (9). Columns: nation_id, name, short_name, gov_type, capital, ruler, relation_to_tempest.

### dim_arcs.csv
One row per story arc (12), in reading order. Columns: arc_id, sequence_no, name, ln_volumes, anime_coverage.

### dim_skills.csv
One row per skill (40). Columns: skill_id, name, skill_type, category. Skill type is Unique, Ultimate, Extra, Intrinsic, or Resist.

### dim_factions.csv
One row per faction (11). Columns: faction_id, name, kind, aligned_with.

### bridge_character_skills.csv
One row per character-skill pair. Columns: character_id, character, skill_id, skill, skill_type, skill_category, acquisition. Use it for "skills per character" and "who holds this skill" views.

### bridge_character_factions.csv
One row per character-faction membership. Columns: character_id, character, faction_id, faction, aligned_with, role. A character can appear in several factions.

### fact_evolutions.csv
One row per evolution step, ordered by character then step_no. Columns: evolution_id, character_id, character, step_no, from_form, to_form, trigger, arc_id, arc.

### demon_lords.csv
One row per demon lord (11). Columns: character_id, character, title, roster, is_awakened, domain, ep_estimate, threat_rank.

### true_dragons.csv
One row per True Dragon (4), in birth order. Columns: character_id, character, epithet, element, birth_order, status, ep_estimate.

## A note on Existence Points

`ep_estimate` is populated for the top tier of characters where the light novels
or the fan wiki give a figure, and left blank otherwise. The numbers are late-story
peaks and are approximate, so treat the EP charts as a ranking of the strongest
named characters rather than an exact measure. `threat_rank` is the canon danger
class and is filled in for every character, so it is the better field for broad
distribution charts.
