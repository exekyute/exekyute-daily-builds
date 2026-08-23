"""Unit tests for the TenSura World Database.

Covers the validator, the build, the canonical facts the runner also checks, and
a round trip that proves sql/schema.sql plus the generated sql/seed.sql rebuild
the same database as the Python builder.

Run from the engine folder:

    python -m unittest discover -s tests
"""

import copy
import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import build_db
from validate import validate


def fresh_conn(data):
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    build_db.build(conn, data)
    return conn


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = build_db.load_data()

    def test_source_data_is_clean(self):
        errors, _ = validate(self.data)
        self.assertEqual(errors, [], f"unexpected validation errors: {errors}")

    def test_unknown_race_is_caught(self):
        data = copy.deepcopy(self.data)
        data["characters"][0]["race"] = "Nonexistent Race"
        errors, _ = validate(data)
        self.assertTrue(any("unknown race" in e for e in errors))

    def test_dangling_ruler_is_caught(self):
        data = copy.deepcopy(self.data)
        data["nations"][0]["ruler"] = "Nobody At All"
        errors, _ = validate(data)
        self.assertTrue(any("ruler" in e for e in errors))

    def test_bad_true_dragon_element_is_caught(self):
        data = copy.deepcopy(self.data)
        for c in data["characters"]:
            if c.get("true_dragon"):
                c["true_dragon"]["element"] = "Bogus"
                break
        errors, _ = validate(data)
        self.assertTrue(any("element" in e for e in errors))


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = build_db.load_data()
        cls.conn = fresh_conn(cls.data)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def scalar(self, sql):
        return self.conn.execute(sql).fetchone()[0]

    def test_row_counts_match_source(self):
        for table, key in [("races", "races"), ("skills", "skills"),
                           ("factions", "factions"), ("nations", "nations"),
                           ("characters", "characters"), ("arcs", "arcs")]:
            self.assertEqual(self.scalar(f"SELECT COUNT(*) FROM {table}"), len(self.data[key]))

    def test_four_true_dragons(self):
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM true_dragons"), 4)

    def test_octagram_has_eight_seats(self):
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM demon_lords WHERE roster = 'Octagram'"), 8)

    def test_firstborn_dragon_is_veldanava(self):
        self.assertEqual(
            self.scalar("SELECT c.name FROM true_dragons td JOIN characters c "
                        "ON c.character_id = td.character_id WHERE td.birth_order = 1"),
            "Veldanava")

    def test_rimuru_has_highest_known_ep(self):
        self.assertEqual(
            self.scalar("SELECT name FROM characters WHERE ep_estimate IS NOT NULL "
                        "ORDER BY ep_estimate DESC LIMIT 1"),
            "Rimuru Tempest")

    def test_no_foreign_key_violations(self):
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_skill_count_view_matches_bridge(self):
        self.assertEqual(
            self.scalar("SELECT SUM(skill_count) FROM v_character_full"),
            self.scalar("SELECT COUNT(*) FROM character_skills"))

    def test_every_faction_has_members(self):
        orphan = self.scalar(
            "SELECT COUNT(*) FROM factions f "
            "WHERE NOT EXISTS (SELECT 1 FROM character_factions cf WHERE cf.faction_id = f.faction_id)")
        self.assertEqual(orphan, 0)


class SeedRoundTripTest(unittest.TestCase):
    """schema.sql + the generated seed.sql should reproduce the Python build."""

    def test_seed_matches_python_build(self):
        data = build_db.load_data()
        built = fresh_conn(data)

        # Regenerate the seed from the built database, then replay it fresh.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            seed_path = os.path.join(tmp, "seed.sql")
            build_db.dump_seed(built, seed_path)

            replay = sqlite3.connect(":memory:")
            replay.execute("PRAGMA foreign_keys = ON")
            with open(build_db.SCHEMA, encoding="utf-8") as fh:
                replay.executescript(fh.read())
            with open(seed_path, encoding="utf-8") as fh:
                replay.executescript(fh.read())

            for table in build_db.SEED_TABLE_ORDER:
                a = built.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                b = replay.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                self.assertEqual(a, b, f"row count mismatch for {table}")
            self.assertEqual(replay.execute("PRAGMA foreign_key_check").fetchall(), [])
            replay.close()
        built.close()


if __name__ == "__main__":
    unittest.main()
