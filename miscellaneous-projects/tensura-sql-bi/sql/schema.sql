-- TenSura World Database: schema
--
-- A small relational model of the world of "That Time I Got Reincarnated as a
-- Slime" (Tensei Shitara Slime Datta Ken). Eleven tables: five dimension tables
-- (races, nations, arcs, skills, factions), one central entity table
-- (characters), two bridge tables for the many-to-many links (character_skills,
-- character_factions), one ordered history table (evolutions), and two subtype
-- tables that add detail for a slice of characters (demon_lords, true_dragons).
--
-- Runs on SQLite, one file, no server. Build it with engine/build_db.py, or load
-- it by hand: sqlite3 tensura.db ".read sql/schema.sql" ".read sql/seed.sql".

PRAGMA foreign_keys = ON;

-- Dimension: species and their place in the evolution ladder.
CREATE TABLE races (
    race_id        INTEGER PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE,
    category       TEXT NOT NULL,   -- Monster, Humanoid, Human, Demon, Dragon, Spirit, Undead, Beastfolk, Giant, Winged
    tier           TEXT NOT NULL,   -- Base or Evolved
    notes          TEXT
);

-- Dimension: story arcs, in reading order, tied to light-novel volumes.
CREATE TABLE arcs (
    arc_id         INTEGER PRIMARY KEY,
    sequence_no    INTEGER NOT NULL UNIQUE,
    name           TEXT NOT NULL UNIQUE,
    ln_volumes     TEXT,            -- light-novel volume span, e.g. "Vol 7-8"
    anime_coverage TEXT,            -- rough anime coverage, where adapted
    summary        TEXT
);

-- Dimension: skills, grouped by the in-universe skill tiers and a rough category.
CREATE TABLE skills (
    skill_id       INTEGER PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE,
    skill_type     TEXT NOT NULL,   -- Unique Skill, Ultimate Skill, Extra Skill, Intrinsic Skill, Resist Skill
    category       TEXT,            -- Analysis, Predation, Manipulation, Elemental, Spatial, Support, Combat
    notes          TEXT
);

-- Dimension: cross-cutting groups a character can belong to (beyond their nation).
CREATE TABLE factions (
    faction_id     INTEGER PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE,
    kind           TEXT,            -- Government, Council, Military, Order, Guild, Demon group
    aligned_with   TEXT,            -- Tempest, Antagonist, Neutral, Independent
    notes          TEXT
);

-- Dimension: nations and their standing with Rimuru's federation.
-- ruler_character_id is a soft reference to characters(character_id): it points
-- at the modelled ruler where there is one, and stays NULL otherwise. It is not
-- a hard foreign key because nations and characters reference each other, and a
-- soft link keeps the load order simple for both the Python and pure-SQL paths.
CREATE TABLE nations (
    nation_id           INTEGER PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE,
    short_name          TEXT,
    gov_type            TEXT,       -- Federation, Monarchy, Theocracy, Empire, Magocracy, Demon Lord state
    capital             TEXT,
    ruler_character_id  INTEGER,    -- soft reference to characters(character_id)
    relation_to_tempest TEXT,       -- Self, Ally, Rival, Enemy, Former Enemy, Neutral
    notes               TEXT
);

-- Central entity: characters, with a race, a home nation, a debut arc, and the
-- canon strength markers (threat rank, demon-lord class, and a wiki-cited EP).
CREATE TABLE characters (
    character_id      INTEGER PRIMARY KEY,
    name              TEXT NOT NULL,
    epithet           TEXT,         -- alias or title, e.g. "Storm Dragon"
    race_id           INTEGER NOT NULL REFERENCES races(race_id),
    nation_id         INTEGER REFERENCES nations(nation_id),
    gender            TEXT,         -- Male, Female, None
    role_title        TEXT,
    alignment         TEXT,         -- Tempest, Ally, Antagonist, Neutral
    status            TEXT,         -- Alive, Deceased, Sealed, Revived, Unknown
    debut_arc_id      INTEGER REFERENCES arcs(arc_id),
    threat_rank       TEXT,         -- F, E, D, C, B, A, A+, Special A, S, Special S, Demon Lord
    demon_lord_class  TEXT,         -- None, Self-Proclaimed, Awakened
    ep_estimate       INTEGER,      -- Existence Points, wiki-cited figure (nullable)
    notes             TEXT
);

-- Bridge: which characters hold which skills (many-to-many).
CREATE TABLE character_skills (
    character_id   INTEGER NOT NULL REFERENCES characters(character_id),
    skill_id       INTEGER NOT NULL REFERENCES skills(skill_id),
    acquisition    TEXT,            -- Initial, Post-Awakening, Post-Evolution, Granted
    PRIMARY KEY (character_id, skill_id)
);

-- Bridge: which characters belong to which factions (many-to-many).
CREATE TABLE character_factions (
    character_id   INTEGER NOT NULL REFERENCES characters(character_id),
    faction_id     INTEGER NOT NULL REFERENCES factions(faction_id),
    role           TEXT,
    PRIMARY KEY (character_id, faction_id)
);

-- History: a character's evolution steps, ordered by step_no.
CREATE TABLE evolutions (
    evolution_id   INTEGER PRIMARY KEY,
    character_id   INTEGER NOT NULL REFERENCES characters(character_id),
    step_no        INTEGER NOT NULL,
    from_form      TEXT NOT NULL,
    to_form        TEXT NOT NULL,
    trigger        TEXT,            -- Naming, Harvest Festival, Demon Lord Seed, Soul absorption
    arc_id         INTEGER REFERENCES arcs(arc_id),
    UNIQUE (character_id, step_no)
);

-- Subtype: extra detail for characters who are Demon Lords.
CREATE TABLE demon_lords (
    character_id   INTEGER PRIMARY KEY REFERENCES characters(character_id),
    title          TEXT,            -- epithet as a Demon Lord, e.g. "Destroyer"
    roster         TEXT,            -- Ten Great Demon Lords, Octagram, Former
    is_awakened    INTEGER NOT NULL DEFAULT 0,  -- 1 if an Awakened (True) Demon Lord
    domain         TEXT,
    notes          TEXT
);

-- Subtype: extra detail for the four True Dragons.
CREATE TABLE true_dragons (
    character_id   INTEGER PRIMARY KEY REFERENCES characters(character_id),
    epithet        TEXT,            -- Star King Dragon, Frost Dragon, Scorch Dragon, Storm Dragon
    element        TEXT,            -- Star, Frost, Scorch, Storm
    birth_order    INTEGER,         -- 1 = firstborn
    status         TEXT,
    notes          TEXT
);

-- Convenience view: characters flattened with their dimension names, plus the
-- subtype flags. This is what the BI export characters.csv is built from, so a
-- single-table connection in Tableau or Power BI already has readable labels.
CREATE VIEW v_character_full AS
SELECT
    c.character_id,
    c.name,
    c.epithet,
    r.name          AS race,
    r.category      AS race_category,
    r.tier          AS race_tier,
    n.name          AS nation,
    n.relation_to_tempest,
    c.gender,
    c.role_title,
    c.alignment,
    c.status,
    a.name          AS debut_arc,
    a.sequence_no   AS debut_arc_no,
    c.threat_rank,
    c.demon_lord_class,
    c.ep_estimate,
    CASE WHEN dl.character_id IS NOT NULL THEN 1 ELSE 0 END AS is_demon_lord,
    dl.roster       AS demon_lord_roster,
    CASE WHEN td.character_id IS NOT NULL THEN 1 ELSE 0 END AS is_true_dragon,
    (SELECT COUNT(*) FROM character_skills cs WHERE cs.character_id = c.character_id) AS skill_count,
    (SELECT COUNT(*) FROM evolutions e WHERE e.character_id = c.character_id)         AS evolution_steps
FROM characters c
JOIN races r         ON r.race_id = c.race_id
LEFT JOIN nations n  ON n.nation_id = c.nation_id
LEFT JOIN arcs a     ON a.arc_id = c.debut_arc_id
LEFT JOIN demon_lords dl ON dl.character_id = c.character_id
LEFT JOIN true_dragons td ON td.character_id = c.character_id;

-- Convenience view: one row per nation with its member count.
CREATE VIEW v_nation_roster AS
SELECT
    n.nation_id,
    n.name,
    n.relation_to_tempest,
    COUNT(c.character_id) AS member_count
FROM nations n
LEFT JOIN characters c ON c.nation_id = n.nation_id
GROUP BY n.nation_id, n.name, n.relation_to_tempest;

-- Helpful indexes for the joins the analytical queries lean on.
CREATE INDEX idx_characters_race   ON characters(race_id);
CREATE INDEX idx_characters_nation ON characters(nation_id);
CREATE INDEX idx_characters_arc    ON characters(debut_arc_id);
CREATE INDEX idx_cs_skill          ON character_skills(skill_id);
CREATE INDEX idx_cf_faction        ON character_factions(faction_id);
CREATE INDEX idx_evolutions_char   ON evolutions(character_id);
