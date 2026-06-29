"""Query the FF7 materia knowledge graph.

Run build_index.py first to create ff7graph.db, then ask the graph questions:

    python query.py stats
    python query.py show Fire
    python query.py find --category summon
    python query.py find --element fire
    python query.py find --at "Gold Saucer"
    python query.py path Fire Ifrit
    python query.py combos All
    python query.py context Bahamut --json

Standard library only: json, sqlite3, argparse.
"""

import argparse
import json
import os
import sqlite3
import sys

from ff7_graph import Graph

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB_PATH = os.path.join(ROOT, "ff7graph.db")

ARROW = {"out": "->", "in": "<-"}


def load_graph(db_path):
    if not os.path.exists(db_path):
        print("No graph found. Run this first:\n    python build_index.py")
        return None
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        nodes = [{"id": r["id"], "type": r["type"], "label": r["label"],
                  "attrs": json.loads(r["attrs"] or "{}")}
                 for r in conn.execute("SELECT id, type, label, attrs FROM nodes")]
        edges = [{"src": r["src"], "rel": r["rel"], "dst": r["dst"],
                  "attrs": json.loads(r["attrs"] or "{}")}
                 for r in conn.execute("SELECT src, rel, dst, attrs FROM edges")]
    finally:
        conn.close()
    return Graph.from_records(nodes, edges)


def resolve_or_warn(graph, term):
    nid = graph.resolve(term)
    if nid is None:
        print("Nothing in the graph matches '%s'. Try: python query.py find --text %s" % (term, term))
    return nid


def cmd_stats(graph, args):
    counts = graph.counts()
    print("%d nodes, %d edges" % (counts["nodes"], counts["edges"]))
    print("\nNodes by type:")
    for ntype in sorted(counts["nodes_by_type"]):
        print("  %-10s %d" % (ntype, counts["nodes_by_type"][ntype]))
    print("\nEdges by relation:")
    for rel in sorted(counts["edges_by_rel"]):
        print("  %-12s %d" % (rel, counts["edges_by_rel"][rel]))
    return 0


def cmd_show(graph, args):
    nid = resolve_or_warn(graph, args.name)
    if nid is None:
        return 1
    node = graph.nodes[nid]
    attrs = node["attrs"]
    print("%s  (%s)" % (node["label"], node["type"]))
    if attrs.get("category_name"):
        print("Category: %s (%s)" % (attrs["category_name"], attrs.get("color", "")))
    if attrs.get("elements"):
        print("Element:  %s" % ", ".join(attrs["elements"]))
    if attrs.get("abilities"):
        print("Grants:   %s" % ", ".join(attrs["abilities"]))
    if attrs.get("found_at"):
        print("Found at: %s" % ", ".join(attrs["found_at"]))
    if attrs.get("notes"):
        print("Notes:    %s" % attrs["notes"])

    groups = {}
    for hop in graph.neighbors(nid):
        key = "%s %s" % (hop["rel"], ARROW[hop["direction"]])
        groups.setdefault(key, []).append((hop["node"]["label"], hop["attrs"]))
    if groups:
        print("\nLinks:")
        for key in sorted(groups):
            labels = sorted(groups[key], key=lambda pair: pair[0].lower())
            effects = [a.get("effect") for _, a in labels if a.get("effect")]
            names = ", ".join(name for name, _ in labels)
            print("  %-16s %s" % (key, names))
            for effect in effects:
                print("        %s" % effect)
    return 0


def cmd_find(graph, args):
    results = graph.find(category=args.category, element=args.element,
                         location=args.at, ability=args.ability, text=args.text)
    if not results:
        print("No materia matched those filters.")
        return 0
    print("%d match%s:" % (len(results), "" if len(results) == 1 else "es"))
    for node in results:
        attrs = node["attrs"]
        tail = attrs.get("category_name", "")
        if attrs.get("elements"):
            tail += " / " + ", ".join(attrs["elements"])
        print("  %-22s %s" % (node["label"], tail))
    return 0


def cmd_path(graph, args):
    start = resolve_or_warn(graph, args.start)
    goal = resolve_or_warn(graph, args.goal)
    if start is None or goal is None:
        return 1
    chain = graph.shortest_path(start, goal)
    if not chain:
        print("No path connects %s and %s." % (graph.nodes[start]["label"], graph.nodes[goal]["label"]))
        return 0
    hops = len(chain) - 1
    print("%s to %s  (%d hop%s)" % (graph.nodes[start]["label"], graph.nodes[goal]["label"],
                                    hops, "" if hops == 1 else "s"))

    def labelled(node):
        if node["type"] == "materia":
            return node["label"]
        return "%s (%s)" % (node["label"], node["type"])

    parts = [labelled(chain[0]["node"])]
    for step in chain[1:]:
        link = "-[%s]->" % step["rel"] if step["direction"] == "out" else "<-[%s]-" % step["rel"]
        parts.append(link)
        parts.append(labelled(step["node"]))
    print("  " + " ".join(parts))
    return 0


def cmd_combos(graph, args):
    nid = resolve_or_warn(graph, args.name)
    if nid is None:
        return 1
    found = False
    for hop in graph.neighbors(nid):
        if hop["rel"] != "PAIRS_WITH":
            continue
        found = True
        other = hop["node"]["label"]
        effect = hop["attrs"].get("effect", "")
        slot = hop["attrs"].get("slot", "")
        if hop["direction"] == "out":
            print("  %s + %s" % (graph.nodes[nid]["label"], other))
        else:
            print("  %s + %s" % (other, graph.nodes[nid]["label"]))
        if slot:
            print("    slot: %s" % slot)
        print("    %s" % effect)
    if not found:
        print("%s has no listed combos." % graph.nodes[nid]["label"])
    return 0


def cmd_context(graph, args):
    nid = resolve_or_warn(graph, args.name)
    if nid is None:
        return 1
    pack = graph.context(nid)
    if args.json:
        print(json.dumps(pack, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(pack, ensure_ascii=False))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Query the FF7 materia knowledge graph.")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("stats", help="node and edge counts")

    p_show = sub.add_parser("show", help="show one node and everything it links to")
    p_show.add_argument("name")

    p_find = sub.add_parser("find", help="list materia by category, element, location, ability, or text")
    p_find.add_argument("--category")
    p_find.add_argument("--element")
    p_find.add_argument("--at", help="found-at location")
    p_find.add_argument("--ability")
    p_find.add_argument("--text", help="substring of the name or notes")

    p_path = sub.add_parser("path", help="shortest path between two nodes")
    p_path.add_argument("start")
    p_path.add_argument("goal")

    p_combos = sub.add_parser("combos", help="support-materia pairings for a materia")
    p_combos.add_argument("name")

    p_context = sub.add_parser("context", help="compact JSON bundle: a node plus its neighbors")
    p_context.add_argument("name")
    p_context.add_argument("--json", action="store_true", help="pretty-print the JSON")

    return parser


COMMANDS = {
    "stats": cmd_stats,
    "show": cmd_show,
    "find": cmd_find,
    "path": cmd_path,
    "combos": cmd_combos,
    "context": cmd_context,
}


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    graph = load_graph(DB_PATH)
    if graph is None:
        return 1
    return COMMANDS[args.command](graph, args)


if __name__ == "__main__":
    sys.exit(main())
