"""Build the TenSura World Database from data/tensura.json.

Reads the single source of truth, validates it, then produces three things from
that one file:

  1. tensura.db      a SQLite database built from sql/schema.sql,
  2. sql/seed.sql    INSERT statements, so the database can also be rebuilt with
                     nothing but the sqlite3 command line,
  3. exports/*.csv one flat CSV per table, for anything that reads CSVs.

Python standard library only. Run it from the engine folder:

    python build_db.py
"""

import csv
import json
import os
import sqlite3
import sys

from validate import validate

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data", "tensura.json")
SCHEMA = os.path.join(ROOT, "sql", "schema.sql")
SEED = os.path.join(ROOT, "sql", "seed.sql")
DB = os.path.join(ROOT, "tensura.db")
EXPORTS = os.path.join(ROOT, "exports")

# The tables, in an order that satisfies the foreign keys, for the seed dump.
SEED_TABLE_ORDER = [
    "races", "arcs", "skills", "factions", "nations", "characters",
    "character_skills", "character_factions", "evolutions",
    "demon_lords", "true_dragons",
]


def load_data(path=DATA):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _id_map(rows, key="name"):
    """Assign 1-based ids in list order and return {name: id}."""
    return {r[key]: i for i, r in enumerate(rows, start=1)}


def build(conn, data):
    """Create the schema in conn and insert every row. Returns the id maps."""
    with open(SCHEMA, encoding="utf-8") as fh:
        conn.executescript(fh.read())

    race_id = _id_map(data["races"])
    skill_id = _id_map(data["skills"])
    faction_id = _id_map(data["factions"])
    nation_id = _id_map(data["nations"])
    char_id = {c["name"]: i for i, c in enumerate(data["characters"], start=1)}
    # Arc ids are just their reading-order sequence numbers.

    cur = conn.cursor()

    cur.executemany(
        "INSERT INTO races (race_id,name,category,tier,notes) VALUES (?,?,?,?,?)",
        [(race_id[r["name"]], r["name"], r["category"], r["tier"], r.get("notes"))
         for r in data["races"]],
    )
    cur.executemany(
        "INSERT INTO arcs (arc_id,sequence_no,name,ln_volumes,anime_coverage,summary) VALUES (?,?,?,?,?,?)",
        [(a["sequence_no"], a["sequence_no"], a["name"], a.get("ln_volumes"),
          a.get("anime_coverage"), a.get("summary")) for a in data["arcs"]],
    )
    cur.executemany(
        "INSERT INTO skills (skill_id,name,skill_type,category,notes) VALUES (?,?,?,?,?)",
        [(skill_id[s["name"]], s["name"], s["skill_type"], s.get("category"), s.get("notes"))
         for s in data["skills"]],
    )
    cur.executemany(
        "INSERT INTO factions (faction_id,name,kind,aligned_with,notes) VALUES (?,?,?,?,?)",
        [(faction_id[f["name"]], f["name"], f.get("kind"), f.get("aligned_with"), f.get("notes"))
         for f in data["factions"]],
    )
    cur.executemany(
        "INSERT INTO nations (nation_id,name,short_name,gov_type,capital,ruler_character_id,relation_to_tempest,notes) "
        "VALUES (?,?,?,?,?,?,?,?)",
        [(nation_id[n["name"]], n["name"], n.get("short_name"), n.get("gov_type"), n.get("capital"),
          char_id.get(n["ruler"]) if n.get("ruler") else None,
          n.get("relation_to_tempest"), n.get("notes")) for n in data["nations"]],
    )

    for c in data["characters"]:
        cur.execute(
            "INSERT INTO characters (character_id,name,epithet,race_id,nation_id,gender,role_title,"
            "alignment,status,debut_arc_id,threat_rank,demon_lord_class,ep_estimate,notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (char_id[c["name"]], c["name"], c.get("epithet"), race_id[c["race"]],
             nation_id.get(c["nation"]) if c.get("nation") else None, c.get("gender"),
             c.get("role_title"), c.get("alignment"), c.get("status"), c.get("debut_arc"),
             c.get("threat_rank"), c.get("demon_lord_class"), c.get("ep_estimate"), c.get("notes")),
        )

    evo_id = 0
    for c in data["characters"]:
        cid = char_id[c["name"]]
        for s in c.get("skills", []):
            cur.execute(
                "INSERT INTO character_skills (character_id,skill_id,acquisition) VALUES (?,?,?)",
                (cid, skill_id[s["skill"]], s.get("acquisition")),
            )
        for f in c.get("factions", []):
            cur.execute(
                "INSERT INTO character_factions (character_id,faction_id,role) VALUES (?,?,?)",
                (cid, faction_id[f["faction"]], f.get("role")),
            )
        for step, e in enumerate(c.get("evolutions", []), start=1):
            evo_id += 1
            cur.execute(
                "INSERT INTO evolutions (evolution_id,character_id,step_no,from_form,to_form,trigger,arc_id) "
                "VALUES (?,?,?,?,?,?,?)",
                (evo_id, cid, step, e["from"], e["to"], e.get("trigger"), e.get("arc")),
            )
        dl = c.get("demon_lord")
        if dl:
            cur.execute(
                "INSERT INTO demon_lords (character_id,title,roster,is_awakened,domain,notes) VALUES (?,?,?,?,?,?)",
                (cid, dl.get("title"), dl.get("roster"), 1 if dl.get("is_awakened") else 0,
                 dl.get("domain"), dl.get("notes")),
            )
        td = c.get("true_dragon")
        if td:
            cur.execute(
                "INSERT INTO true_dragons (character_id,epithet,element,birth_order,status,notes) VALUES (?,?,?,?,?,?)",
                (cid, td.get("epithet"), td.get("element"), td.get("birth_order"),
                 td.get("status"), td.get("notes")),
            )

    conn.commit()
    return {"race": race_id, "skill": skill_id, "faction": faction_id,
            "nation": nation_id, "char": char_id}


def _sql_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def dump_seed(conn, path=SEED):
    """Write INSERT statements for every table so the DB can be rebuilt in pure SQL."""
    cur = conn.cursor()
    lines = [
        "-- TenSura World Database: seed data",
        "-- Generated by engine/build_db.py from data/tensura.json. Do not edit by hand.",
        "-- Load with: sqlite3 tensura.db \".read sql/schema.sql\" \".read sql/seed.sql\"",
        "",
        "BEGIN TRANSACTION;",
        "",
    ]
    for table in SEED_TABLE_ORDER:
        cols = [row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()]
        collist = ",".join(cols)
        rows = cur.execute(f"SELECT {collist} FROM {table}").fetchall()
        lines.append(f"-- {table} ({len(rows)} rows)")
        for r in rows:
            values = ",".join(_sql_literal(v) for v in r)
            lines.append(f"INSERT INTO {table} ({collist}) VALUES ({values});")
        lines.append("")
    lines.append("COMMIT;")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


# Each export is (filename, SQL). Character-facing tables carry both the id keys
# (for relationship modelling) and readable label columns (for quick single-table
# charts), so either BI approach works without extra joins.
EXPORT_QUERIES = {
    "dim_races.csv": "SELECT race_id, name, category, tier FROM races ORDER BY race_id",
    "dim_nations.csv":
        "SELECT n.nation_id, n.name, n.short_name, n.gov_type, n.capital, "
        "rc.name AS ruler, n.relation_to_tempest "
        "FROM nations n LEFT JOIN characters rc ON rc.character_id = n.ruler_character_id "
        "ORDER BY n.nation_id",
    "dim_arcs.csv":
        "SELECT arc_id, sequence_no, name, ln_volumes, anime_coverage FROM arcs ORDER BY sequence_no",
    "dim_skills.csv": "SELECT skill_id, name, skill_type, category FROM skills ORDER BY skill_id",
    "dim_factions.csv": "SELECT faction_id, name, kind, aligned_with FROM factions ORDER BY faction_id",
    "characters.csv":
        "SELECT c.character_id, c.name, c.epithet, "
        "c.race_id, r.name AS race, r.category AS race_category, r.tier AS race_tier, "
        "c.nation_id, n.name AS nation, n.relation_to_tempest, "
        "c.debut_arc_id, a.name AS debut_arc, a.sequence_no AS debut_arc_no, "
        "c.gender, c.role_title, c.alignment, c.status, "
        "c.threat_rank, c.demon_lord_class, c.ep_estimate, "
        "CASE WHEN dl.character_id IS NOT NULL THEN 1 ELSE 0 END AS is_demon_lord, "
        "dl.roster AS demon_lord_roster, "
        "CASE WHEN td.character_id IS NOT NULL THEN 1 ELSE 0 END AS is_true_dragon, "
        "(SELECT COUNT(*) FROM character_skills cs WHERE cs.character_id = c.character_id) AS skill_count, "
        "(SELECT COUNT(*) FROM evolutions e WHERE e.character_id = c.character_id) AS evolution_steps "
        "FROM characters c "
        "JOIN races r ON r.race_id = c.race_id "
        "LEFT JOIN nations n ON n.nation_id = c.nation_id "
        "LEFT JOIN arcs a ON a.arc_id = c.debut_arc_id "
        "LEFT JOIN demon_lords dl ON dl.character_id = c.character_id "
        "LEFT JOIN true_dragons td ON td.character_id = c.character_id "
        "ORDER BY c.character_id",
    "bridge_character_skills.csv":
        "SELECT cs.character_id, c.name AS character, cs.skill_id, s.name AS skill, "
        "s.skill_type, s.category AS skill_category, cs.acquisition "
        "FROM character_skills cs "
        "JOIN characters c ON c.character_id = cs.character_id "
        "JOIN skills s ON s.skill_id = cs.skill_id "
        "ORDER BY cs.character_id, cs.skill_id",
    "bridge_character_factions.csv":
        "SELECT cf.character_id, c.name AS character, cf.faction_id, f.name AS faction, "
        "f.aligned_with, cf.role "
        "FROM character_factions cf "
        "JOIN characters c ON c.character_id = cf.character_id "
        "JOIN factions f ON f.faction_id = cf.faction_id "
        "ORDER BY cf.character_id, cf.faction_id",
    "fact_evolutions.csv":
        "SELECT e.evolution_id, e.character_id, c.name AS character, e.step_no, "
        "e.from_form, e.to_form, e.trigger, e.arc_id, a.name AS arc "
        "FROM evolutions e "
        "JOIN characters c ON c.character_id = e.character_id "
        "LEFT JOIN arcs a ON a.arc_id = e.arc_id "
        "ORDER BY e.character_id, e.step_no",
    "demon_lords.csv":
        "SELECT dl.character_id, c.name AS character, dl.title, dl.roster, dl.is_awakened, "
        "dl.domain, c.ep_estimate, c.threat_rank "
        "FROM demon_lords dl JOIN characters c ON c.character_id = dl.character_id "
        "ORDER BY dl.character_id",
    "true_dragons.csv":
        "SELECT td.character_id, c.name AS character, td.epithet, td.element, td.birth_order, "
        "td.status, c.ep_estimate "
        "FROM true_dragons td JOIN characters c ON c.character_id = td.character_id "
        "ORDER BY td.birth_order",
}


def export_csvs(conn, folder=EXPORTS):
    os.makedirs(folder, exist_ok=True)
    cur = conn.cursor()
    for filename, sql in EXPORT_QUERIES.items():
        cur.execute(sql)
        headers = [d[0] for d in cur.description]
        rows = cur.fetchall()
        with open(os.path.join(folder, filename), "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            writer.writerows(rows)
    return list(EXPORT_QUERIES)


def main():
    data = load_data()
    errors, warnings = validate(data)
    for w in warnings:
        print(f"  warning: {w}")
    if errors:
        print(f"\nBUILD FAILED: {len(errors)} error(s) in data/tensura.json")
        for e in errors:
            print(f"  error: {e}")
        sys.exit(1)

    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    build(conn, data)
    dump_seed(conn)
    exported = export_csvs(conn)

    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in SEED_TABLE_ORDER}
    conn.close()

    print("\nBuilt tensura.db")
    for t in SEED_TABLE_ORDER:
        print(f"  {t:<22} {counts[t]:>4} rows")
    print(f"\nWrote sql/seed.sql and {len(exported)} CSVs to exports/")


if __name__ == "__main__":
    main()
