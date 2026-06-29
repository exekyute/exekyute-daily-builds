"""Pure graph model and algorithms for the FF7 materia knowledge graph.

No file or database access happens here. Everything works on plain Python
dictionaries and lists, which is what keeps the logic easy to read and test.

The graph has five kinds of node:

    materia      one materia (Fire, Bahamut, All, Steal, ...)
    category     Magic, Summon, Support, Command, Independent
    element      Fire, Ice, Lightning, ...
    ability      a spell or command a materia grants (Fire2, D.Blow, ...)
    location     where a materia is first found (Item Shops, Gold Saucer, ...)

and five kinds of edge:

    BELONGS_TO    materia -> category
    HAS_ELEMENT   materia -> element
    GRANTS        materia -> ability
    FOUND_AT      materia -> location
    PAIRS_WITH    support materia -> the materia it links with (carries an effect)
"""

import re
from collections import deque

# Node types.
NODE_MATERIA = "materia"
NODE_CATEGORY = "category"
NODE_ELEMENT = "element"
NODE_ABILITY = "ability"
NODE_LOCATION = "location"

# Edge relations.
REL_BELONGS_TO = "BELONGS_TO"
REL_HAS_ELEMENT = "HAS_ELEMENT"
REL_GRANTS = "GRANTS"
REL_FOUND_AT = "FOUND_AT"
REL_PAIRS_WITH = "PAIRS_WITH"


def slug(text):
    """Turn a label into a lowercase, hyphen-separated key.

    'Gold Saucer' -> 'gold-saucer', 'D.Blow' -> 'd-blow', 'HP<->MP' -> 'hp-mp'.
    """
    text = str(text).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def node_id(node_type, key):
    """Build a namespaced id so a Fire materia, the Fire element, and the Fire
    spell never collide: 'materia:fire', 'element:fire', 'ability:fire'."""
    return node_type + ":" + slug(key)


class Graph:
    """A small directed knowledge graph with undirected traversal.

    Edges are stored with a direction, so a query can tell you that Fire
    BELONGS_TO Magic (outgoing) while Magic is the category OF Fire (incoming).
    Path finding walks the graph in both directions.
    """

    def __init__(self):
        self.nodes = {}          # id -> {"id", "type", "label", "attrs"}
        self.edges = []          # list of {"src", "rel", "dst", "attrs"}
        self._out = {}           # id -> list of edge indexes leaving the node
        self._in = {}            # id -> list of edge indexes entering the node

    # -- building -----------------------------------------------------------

    def add_node(self, nid, ntype, label, attrs=None):
        if nid not in self.nodes:
            self.nodes[nid] = {"id": nid, "type": ntype, "label": label, "attrs": attrs or {}}
            self._out[nid] = []
            self._in[nid] = []
        return nid

    def add_edge(self, src, rel, dst, attrs=None):
        if src not in self.nodes or dst not in self.nodes:
            raise KeyError("edge references a node that does not exist: %s -> %s" % (src, dst))
        index = len(self.edges)
        self.edges.append({"src": src, "rel": rel, "dst": dst, "attrs": attrs or {}})
        self._out[src].append(index)
        self._in[dst].append(index)
        return index

    # -- lookup -------------------------------------------------------------

    def resolve(self, term):
        """Find a node id from a user-typed term.

        Accepts a full node id ('materia:fire'), a materia id ('fire'), or any
        node label, matched without caring about case. Materia win ties so that
        typing 'fire' lands on the Fire materia, not the Fire element.
        """
        if not term:
            return None
        term = str(term).strip()
        if term in self.nodes:
            return term
        guess = node_id(NODE_MATERIA, term)
        if guess in self.nodes:
            return guess
        wanted = term.lower()
        matches = [n["id"] for n in self.nodes.values() if n["label"].lower() == wanted]
        if not matches:
            return None
        matches.sort(key=lambda nid: (self.nodes[nid]["type"] != NODE_MATERIA, nid))
        return matches[0]

    def neighbors(self, nid):
        """Return everything one step away, as a list of dicts:
        {"rel", "direction", "node", "attrs"} with direction 'out' or 'in'."""
        result = []
        for index in self._out.get(nid, []):
            edge = self.edges[index]
            result.append({"rel": edge["rel"], "direction": "out",
                           "node": self.nodes[edge["dst"]], "attrs": edge["attrs"]})
        for index in self._in.get(nid, []):
            edge = self.edges[index]
            result.append({"rel": edge["rel"], "direction": "in",
                           "node": self.nodes[edge["src"]], "attrs": edge["attrs"]})
        return result

    def shortest_path(self, start, goal):
        """Breadth-first search treating edges as undirected.

        Returns a list of steps from start to goal. Each step is
        {"node", "rel", "direction"}; the first step's rel is None. Returns an
        empty list when the two nodes are not connected.
        """
        if start not in self.nodes or goal not in self.nodes:
            return []
        if start == goal:
            return [{"node": self.nodes[start], "rel": None, "direction": None}]
        came_from = {start: None}          # node -> (previous node, rel, direction)
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if current == goal:
                break
            for hop in self.neighbors(current):
                nxt = hop["node"]["id"]
                if nxt not in came_from:
                    came_from[nxt] = (current, hop["rel"], hop["direction"])
                    queue.append(nxt)
        if goal not in came_from:
            return []
        chain = []
        node = goal
        while node is not None:
            prev = came_from[node]
            if prev is None:
                chain.append({"node": self.nodes[node], "rel": None, "direction": None})
                node = None
            else:
                previous, rel, direction = prev
                chain.append({"node": self.nodes[node], "rel": rel, "direction": direction})
                node = previous
        chain.reverse()
        return chain

    def find(self, category=None, element=None, location=None, ability=None, text=None):
        """Filter materia nodes by any combination of fields. Returns materia
        node dicts sorted by name."""
        out = []
        for node in self.nodes.values():
            if node["type"] != NODE_MATERIA:
                continue
            attrs = node["attrs"]
            if category and slug(category) not in (attrs.get("category", ""), slug(attrs.get("category_name", ""))):
                continue
            if element and slug(element) not in [slug(e) for e in attrs.get("elements", [])]:
                continue
            if location and slug(location) not in [slug(l) for l in attrs.get("found_at", [])]:
                continue
            if ability and slug(ability) not in [slug(a) for a in attrs.get("abilities", [])]:
                continue
            if text:
                hay = (node["label"] + " " + attrs.get("notes", "")).lower()
                if text.lower() not in hay:
                    continue
            out.append(node)
        out.sort(key=lambda n: n["label"].lower())
        return out

    def context(self, nid):
        """A compact bundle for one node: the node plus its direct neighbors,
        grouped by relation. This is the small, focused answer an assistant
        would want instead of a whole page of text."""
        node = self.nodes.get(nid)
        if node is None:
            return None
        groups = {}
        for hop in self.neighbors(nid):
            key = ("%s %s" % (hop["rel"], "->" if hop["direction"] == "out" else "<-"))
            entry = {"id": hop["node"]["id"], "label": hop["node"]["label"], "type": hop["node"]["type"]}
            if hop["attrs"]:
                entry["via"] = hop["attrs"]
            groups.setdefault(key, []).append(entry)
        for key in groups:
            groups[key].sort(key=lambda e: e["label"].lower())
        return {"id": node["id"], "label": node["label"], "type": node["type"],
                "attrs": node["attrs"], "links": groups}

    def counts(self):
        """Node and edge tallies for the index summary."""
        by_type = {}
        for node in self.nodes.values():
            by_type[node["type"]] = by_type.get(node["type"], 0) + 1
        by_rel = {}
        for edge in self.edges:
            by_rel[edge["rel"]] = by_rel.get(edge["rel"], 0) + 1
        return {"nodes": len(self.nodes), "edges": len(self.edges),
                "nodes_by_type": by_type, "edges_by_rel": by_rel}

    # -- persistence helpers ------------------------------------------------

    def to_records(self):
        """Flatten to (nodes, edges) lists of plain dicts for storage."""
        nodes = [dict(n) for n in self.nodes.values()]
        edges = [dict(e) for e in self.edges]
        return nodes, edges

    @classmethod
    def from_records(cls, nodes, edges):
        """Rebuild a graph from stored (nodes, edges) records."""
        graph = cls()
        for n in nodes:
            graph.add_node(n["id"], n["type"], n["label"], n.get("attrs") or {})
        for e in edges:
            graph.add_edge(e["src"], e["rel"], e["dst"], e.get("attrs") or {})
        return graph


def build_graph(data):
    """Turn a parsed materia.json dict into a Graph.

    This is the indexer's core: it reads the curated fields and lays down the
    nodes and edges. It assumes the data has already passed validation.
    """
    graph = Graph()

    category_names = {c["id"]: c["name"] for c in data.get("categories", [])}
    category_colors = {c["id"]: c.get("color", "") for c in data.get("categories", [])}

    # Category nodes.
    for cat in data.get("categories", []):
        graph.add_node(node_id(NODE_CATEGORY, cat["id"]), NODE_CATEGORY, cat["name"],
                       {"color": cat.get("color", ""), "blurb": cat.get("blurb", "")})

    # Element nodes.
    for element in data.get("elements", []):
        graph.add_node(node_id(NODE_ELEMENT, element), NODE_ELEMENT, element, {})

    # Materia nodes and their edges.
    for m in data.get("materia", []):
        mid = node_id(NODE_MATERIA, m["id"])
        attrs = {
            "category": m["category"],
            "category_name": category_names.get(m["category"], m["category"]),
            "color": category_colors.get(m["category"], ""),
            "elements": m.get("elements", []),
            "abilities": m.get("abilities", []),
            "found_at": m.get("found_at", []),
            "notes": m.get("notes", ""),
        }
        graph.add_node(mid, NODE_MATERIA, m["name"], attrs)

        cat_node = node_id(NODE_CATEGORY, m["category"])
        if cat_node in graph.nodes:
            graph.add_edge(mid, REL_BELONGS_TO, cat_node)

        for element in m.get("elements", []):
            enode = graph.add_node(node_id(NODE_ELEMENT, element), NODE_ELEMENT, element, {})
            graph.add_edge(mid, REL_HAS_ELEMENT, enode)

        for ability in m.get("abilities", []):
            anode = graph.add_node(node_id(NODE_ABILITY, ability), NODE_ABILITY, ability, {})
            graph.add_edge(mid, REL_GRANTS, anode)

        for place in m.get("found_at", []):
            lnode = graph.add_node(node_id(NODE_LOCATION, place), NODE_LOCATION, place, {})
            graph.add_edge(mid, REL_FOUND_AT, lnode)

    # Support combos: PAIRS_WITH edges.
    for combo in data.get("combos", []):
        src = node_id(NODE_MATERIA, combo["support"])
        dst = node_id(NODE_MATERIA, combo["target"])
        if src in graph.nodes and dst in graph.nodes:
            graph.add_edge(src, REL_PAIRS_WITH, dst,
                           {"slot": combo.get("slot", ""), "effect": combo.get("effect", "")})

    return graph
