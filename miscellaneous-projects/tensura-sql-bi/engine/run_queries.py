"""Run the analytical queries and check the database against known facts.

This is the project's test run. It builds a fresh in-memory database straight
from data/tensura.json, prints the result of every query in sql/queries.sql, then
checks a set of hand-verified facts about the world and reports PASS or FAIL.

Standard library only. Run it from the engine folder:

    python run_queries.py
"""

import os
import sqlite3
import sys

import build_db
from validate import validate

ROOT = build_db.ROOT
QUERIES = os.path.join(ROOT, "sql", "queries.sql")


def parse_query_file(path):
    """Split queries.sql into (title, sql) blocks on the '--#' markers."""
    blocks = []
    title, body = None, []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("--#"):
                if title is not None:
                    blocks.append((title, "".join(body).strip()))
                title, body = line[3:].strip(), []
            elif title is not None:
                body.append(line)
    if title is not None:
        blocks.append((title, "".join(body).strip()))
    return blocks


def print_table(headers, rows, limit=15):
    """Print rows as a simple aligned table."""
    str_rows = [["" if v is None else str(v) for v in r] for r in rows[:limit]]
    widths = [len(h) for h in headers]
    for r in str_rows:
        widths = [max(w, len(c)) for w, c in zip(widths, r)]
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    print("  " + line)
    print("  " + "  ".join("-" * w for w in widths))
    for r in str_rows:
        print("  " + "  ".join(c.ljust(w) for c, w in zip(r, widths)))
    if len(rows) > limit:
        print(f"  ... {len(rows) - limit} more row(s)")


def run_queries(conn):
    for i, (title, sql) in enumerate(parse_query_file(QUERIES), start=1):
        cur = conn.execute(sql)
        headers = [d[0] for d in cur.description]
        rows = cur.fetchall()
        print(f"\nQ{i}. {title}")
        print_table(headers, rows)


def scalar(conn, sql):
    return conn.execute(sql).fetchone()[0]


def run_checks(conn, data):
    """A list of (description, actual, expected) hand-verified checks."""
    checks = []

    def check(desc, actual, expected):
        checks.append((desc, actual, expected, actual == expected))

    # 1-5: every row from the source made it in.
    for table, key in [("races", "races"), ("skills", "skills"), ("factions", "factions"),
                        ("nations", "nations"), ("characters", "characters"), ("arcs", "arcs")]:
        check(f"{table} row count matches the source file",
              scalar(conn, f"SELECT COUNT(*) FROM {table}"), len(data[key]))

    # Canonical facts that double as integrity checks.
    check("There are exactly four True Dragons",
          scalar(conn, "SELECT COUNT(*) FROM true_dragons"), 4)
    check("The Octagram seats exactly eight demon lords",
          scalar(conn, "SELECT COUNT(*) FROM demon_lords WHERE roster = 'Octagram'"), 8)
    check("The firstborn True Dragon is Veldanava",
          scalar(conn, "SELECT c.name FROM true_dragons td JOIN characters c "
                       "ON c.character_id = td.character_id WHERE td.birth_order = 1"),
          "Veldanava")
    check("The highest known Existence Points belong to Rimuru Tempest",
          scalar(conn, "SELECT name FROM characters WHERE ep_estimate IS NOT NULL "
                       "ORDER BY ep_estimate DESC LIMIT 1"),
          "Rimuru Tempest")

    # Relational integrity.
    check("No nation ruler points at a missing character",
          scalar(conn, "SELECT COUNT(*) FROM nations WHERE ruler_character_id IS NOT NULL "
                       "AND ruler_character_id NOT IN (SELECT character_id FROM characters)"), 0)
    check("Every character resolves to a known race",
          scalar(conn, "SELECT COUNT(*) FROM characters c "
                       "LEFT JOIN races r ON r.race_id = c.race_id WHERE r.race_id IS NULL"), 0)
    check("The skill_count column equals the bridge row total",
          scalar(conn, "SELECT SUM(skill_count) FROM v_character_full"),
          scalar(conn, "SELECT COUNT(*) FROM character_skills"))
    check("SQLite reports no foreign-key violations",
          len(conn.execute("PRAGMA foreign_key_check").fetchall()), 0)

    return checks


def main():
    data = build_db.load_data()
    errors, warnings = validate(data)
    if errors:
        print("Data failed validation:")
        for e in errors:
            print(f"  error: {e}")
        sys.exit(1)

    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    build_db.build(conn, data)

    run_queries(conn)

    print("\n" + "=" * 60)
    print("CHECKS")
    print("=" * 60)
    checks = run_checks(conn, data)
    passed = 0
    for desc, actual, expected, ok in checks:
        flag = "PASS" if ok else "FAIL"
        passed += ok
        detail = "" if ok else f"  (got {actual!r}, expected {expected!r})"
        print(f"  [{flag}] {desc}{detail}")

    print("-" * 60)
    print(f"  {passed}/{len(checks)} checks passed")
    conn.close()

    if passed != len(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
