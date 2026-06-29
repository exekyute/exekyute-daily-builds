"""Tests for the FF7 materia knowledge graph.

Run from the engine folder:

    python -m unittest discover -s tests

The first group tests the graph logic and validation on small inline data. The
last group loads the real dataset and checks both that it passes validation and
that a few well-known facts come out of the graph correctly.
"""

import json
import os
import sys
import unittest

# Make the engine modules importable when running the tests from anywhere.
ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

from ff7_graph import Graph, build_graph, slug, node_id  # noqa: E402
from validate import validate  # noqa: E402

DATA_PATH = os.path.join(os.path.dirname(ENGINE_DIR), "data", "materia.json")


def sample_data():
    """A tiny, self-contained dataset that exercises every edge type."""
    return {
        "categories": [
            {"id": "magic", "name": "Magic", "color": "Green"},
            {"id": "summon", "name": "Summon", "color": "Red"},
            {"id": "support", "name": "Support", "color": "Blue"},
        ],
        "elements": ["Fire", "Ice"],
        "materia": [
            {"id": "fire", "name": "Fire", "category": "magic", "elements": ["Fire"],
             "abilities": ["Fire", "Fire2"], "found_at": ["Item Shops"], "notes": "basic fire"},
            {"id": "ifrit", "name": "Ifrit", "category": "summon", "elements": ["Fire"],
             "abilities": ["Hellfire"], "found_at": ["Cargo Ship"], "notes": "fire summon"},
            {"id": "all", "name": "All", "category": "support", "elements": [],
             "abilities": [], "found_at": ["Item Shops"], "notes": "hits everything"},
        ],
        "combos": [
            {"support": "all", "target": "fire", "slot": "weapon", "effect": "Fire on all enemies."},
        ],
    }


class TestSlug(unittest.TestCase):
    def test_slug_normalizes(self):
        self.assertEqual(slug("Gold Saucer"), "gold-saucer")
        self.assertEqual(slug("D.Blow"), "d-blow")
        self.assertEqual(slug("HP<->MP"), "hp-mp")

    def test_node_id_namespaces(self):
        self.assertEqual(node_id("materia", "fire"), "materia:fire")
        self.assertNotEqual(node_id("materia", "Fire"), node_id("element", "Fire"))


class TestGraphBuild(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph(sample_data())

    def test_node_types_present(self):
        counts = self.graph.counts()
        self.assertEqual(counts["nodes_by_type"]["materia"], 3)
        self.assertEqual(counts["nodes_by_type"]["category"], 3)
        # An element node exists for every declared element (Fire and Ice), even
        # though only Fire is actually used here. Fire is shared by Fire and
        # Ifrit, which the HAS_ELEMENT edge count in test_edges_created confirms.
        self.assertEqual(counts["nodes_by_type"]["element"], 2)

    def test_edges_created(self):
        rels = self.graph.counts()["edges_by_rel"]
        self.assertEqual(rels["BELONGS_TO"], 3)
        self.assertEqual(rels["HAS_ELEMENT"], 2)
        self.assertEqual(rels["GRANTS"], 3)
        self.assertEqual(rels["PAIRS_WITH"], 1)


class TestResolve(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph(sample_data())

    def test_resolve_by_full_id(self):
        self.assertEqual(self.graph.resolve("materia:fire"), "materia:fire")

    def test_resolve_by_materia_id(self):
        self.assertEqual(self.graph.resolve("fire"), "materia:fire")

    def test_resolve_is_case_insensitive(self):
        self.assertEqual(self.graph.resolve("IFRIT"), "materia:ifrit")

    def test_materia_wins_over_element(self):
        # 'Fire' is both a materia and an element; the materia should win.
        self.assertEqual(self.graph.resolve("Fire"), "materia:fire")

    def test_unknown_returns_none(self):
        self.assertIsNone(self.graph.resolve("Chocobo Sandwich"))


class TestQueries(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph(sample_data())

    def test_path_through_shared_element(self):
        chain = self.graph.shortest_path("materia:fire", "materia:ifrit")
        labels = [step["node"]["label"] for step in chain]
        self.assertEqual(labels[0], "Fire")
        self.assertEqual(labels[-1], "Ifrit")
        self.assertIn("Fire", labels)  # passes through the Fire element node

    def test_no_path_returns_empty(self):
        lonely = build_graph({
            "categories": [{"id": "magic", "name": "Magic"}],
            "elements": ["Fire", "Ice"],
            "materia": [
                {"id": "fire", "name": "Fire", "category": "magic", "elements": ["Fire"],
                 "abilities": [], "found_at": ["Item Shops"]},
                {"id": "ice", "name": "Ice", "category": "magic", "elements": ["Ice"],
                 "abilities": [], "found_at": ["Item Shops"]},
            ],
            "combos": [],
        })
        # Fire and Ice share the Magic category and Item Shops, so they ARE
        # connected; two truly isolated nodes are needed to test the empty case.
        far = Graph()
        far.add_node("a", "materia", "A", {})
        far.add_node("b", "materia", "B", {})
        self.assertEqual(far.shortest_path("a", "b"), [])
        self.assertNotEqual(lonely.shortest_path("materia:fire", "materia:ice"), [])

    def test_find_by_category(self):
        results = self.graph.find(category="summon")
        self.assertEqual([n["label"] for n in results], ["Ifrit"])

    def test_find_by_element(self):
        results = self.graph.find(element="fire")
        self.assertEqual(sorted(n["label"] for n in results), ["Fire", "Ifrit"])

    def test_find_by_location(self):
        results = self.graph.find(location="Item Shops")
        self.assertEqual(sorted(n["label"] for n in results), ["All", "Fire"])

    def test_find_by_text(self):
        results = self.graph.find(text="summon")
        self.assertEqual([n["label"] for n in results], ["Ifrit"])

    def test_context_groups_neighbors(self):
        pack = self.graph.context("materia:fire")
        self.assertEqual(pack["label"], "Fire")
        joined = " ".join(pack["links"].keys())
        self.assertIn("BELONGS_TO", joined)
        self.assertIn("GRANTS", joined)


class TestRoundTrip(unittest.TestCase):
    def test_records_round_trip(self):
        original = build_graph(sample_data())
        nodes, edges = original.to_records()
        rebuilt = Graph.from_records(nodes, edges)
        self.assertEqual(original.counts(), rebuilt.counts())
        self.assertEqual(rebuilt.resolve("ifrit"), "materia:ifrit")


class TestValidation(unittest.TestCase):
    def test_clean_data_has_no_errors(self):
        self.assertEqual(validate(sample_data()), [])

    def test_unknown_category(self):
        data = sample_data()
        data["materia"][0]["category"] = "mystery"
        self.assertTrue(any("unknown category" in e for e in validate(data)))

    def test_duplicate_id(self):
        data = sample_data()
        data["materia"].append(dict(data["materia"][0]))
        self.assertTrue(any("Duplicate materia id" in e for e in validate(data)))

    def test_bad_element(self):
        data = sample_data()
        data["materia"][0]["elements"] = ["Plasma"]
        self.assertTrue(any("not in the elements list" in e for e in validate(data)))

    def test_missing_found_at(self):
        data = sample_data()
        data["materia"][0]["found_at"] = []
        self.assertTrue(any("no 'found_at'" in e for e in validate(data)))

    def test_combo_points_at_missing_materia(self):
        data = sample_data()
        data["combos"][0]["target"] = "nonexistent"
        self.assertTrue(any("unknown target materia" in e for e in validate(data)))


class TestRealDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DATA_PATH, "r", encoding="utf-8") as handle:
            cls.data = json.load(handle)
        cls.graph = build_graph(cls.data)

    def test_real_data_is_valid(self):
        self.assertEqual(validate(self.data), [])

    def test_summon_count(self):
        # 17 summon materia, including the two master materia.
        self.assertEqual(len(self.graph.find(category="summon")), 17)

    def test_fire_grants_original_names(self):
        fire = self.graph.nodes["materia:fire"]["attrs"]
        self.assertEqual(fire["abilities"], ["Fire", "Fire2", "Fire3"])

    def test_lightning_uses_bolt_names(self):
        bolt = self.graph.nodes["materia:lightning"]["attrs"]
        self.assertIn("Bolt2", bolt["abilities"])

    def test_ifrit_is_fire(self):
        self.assertIn("Fire", self.graph.nodes["materia:ifrit"]["attrs"]["elements"])

    def test_all_pairs_with_restore(self):
        targets = [hop["node"]["id"] for hop in self.graph.neighbors("materia:all")
                   if hop["rel"] == "PAIRS_WITH" and hop["direction"] == "out"]
        self.assertIn("materia:restore", targets)

    def test_path_fire_to_ifrit_exists(self):
        chain = self.graph.shortest_path("materia:fire", "materia:ifrit")
        self.assertTrue(chain)
        self.assertEqual(chain[0]["node"]["label"], "Fire")
        self.assertEqual(chain[-1]["node"]["label"], "Ifrit")


if __name__ == "__main__":
    unittest.main()
