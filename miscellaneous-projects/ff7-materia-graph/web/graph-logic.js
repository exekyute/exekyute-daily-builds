// Pure graph logic for the FF7 materia knowledge graph, in the browser.
//
// This is a direct port of engine/ff7_graph.py. It has no DOM access, so it can
// be loaded on its own and tested in tests.html. app.js is the only file that
// touches the page.
//
// Everything is attached to window.FF7Graph so plain <script> tags can use it
// without modules, which keeps the page openable by double-clicking the file.

(function (root) {
  "use strict";

  function slug(text) {
    return String(text)
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function nodeId(type, key) {
    return type + ":" + slug(key);
  }

  var ARROW = { out: "->", in: "<-" };

  function Graph() {
    this.nodes = {};   // id -> {id, type, label, attrs}
    this.edges = [];   // {src, rel, dst, attrs}
    this._out = {};    // id -> [edge index]
    this._in = {};     // id -> [edge index]
  }

  Graph.prototype.addNode = function (id, type, label, attrs) {
    if (!this.nodes[id]) {
      this.nodes[id] = { id: id, type: type, label: label, attrs: attrs || {} };
      this._out[id] = [];
      this._in[id] = [];
    }
    return id;
  };

  Graph.prototype.addEdge = function (src, rel, dst, attrs) {
    if (!this.nodes[src] || !this.nodes[dst]) {
      throw new Error("edge references a missing node: " + src + " -> " + dst);
    }
    var index = this.edges.length;
    this.edges.push({ src: src, rel: rel, dst: dst, attrs: attrs || {} });
    this._out[src].push(index);
    this._in[dst].push(index);
    return index;
  };

  Graph.prototype.resolve = function (term) {
    if (!term) return null;
    term = String(term).trim();
    if (this.nodes[term]) return term;
    var guess = nodeId("materia", term);
    if (this.nodes[guess]) return guess;
    var wanted = term.toLowerCase();
    var matches = [];
    for (var id in this.nodes) {
      if (this.nodes[id].label.toLowerCase() === wanted) matches.push(id);
    }
    if (!matches.length) return null;
    // Materia win ties, then by id.
    matches.sort(function (a, b) {
      var aMat = this.nodes[a].type !== "materia";
      var bMat = this.nodes[b].type !== "materia";
      if (aMat !== bMat) return aMat ? 1 : -1;
      return a < b ? -1 : a > b ? 1 : 0;
    }.bind(this));
    return matches[0];
  };

  Graph.prototype.neighbors = function (id) {
    var result = [];
    var self = this;
    (this._out[id] || []).forEach(function (i) {
      var e = self.edges[i];
      result.push({ rel: e.rel, direction: "out", node: self.nodes[e.dst], attrs: e.attrs });
    });
    (this._in[id] || []).forEach(function (i) {
      var e = self.edges[i];
      result.push({ rel: e.rel, direction: "in", node: self.nodes[e.src], attrs: e.attrs });
    });
    return result;
  };

  Graph.prototype.shortestPath = function (start, goal) {
    if (!this.nodes[start] || !this.nodes[goal]) return [];
    if (start === goal) return [{ node: this.nodes[start], rel: null, direction: null }];
    var cameFrom = {};
    cameFrom[start] = null;
    var queue = [start];
    while (queue.length) {
      var current = queue.shift();
      if (current === goal) break;
      var hops = this.neighbors(current);
      for (var i = 0; i < hops.length; i++) {
        var nxt = hops[i].node.id;
        if (!(nxt in cameFrom)) {
          cameFrom[nxt] = { prev: current, rel: hops[i].rel, direction: hops[i].direction };
          queue.push(nxt);
        }
      }
    }
    if (!(goal in cameFrom)) return [];
    var chain = [];
    var node = goal;
    while (node !== null) {
      var prev = cameFrom[node];
      if (prev === null) {
        chain.push({ node: this.nodes[node], rel: null, direction: null });
        node = null;
      } else {
        chain.push({ node: this.nodes[node], rel: prev.rel, direction: prev.direction });
        node = prev.prev;
      }
    }
    chain.reverse();
    return chain;
  };

  Graph.prototype.find = function (filters) {
    filters = filters || {};
    var out = [];
    for (var id in this.nodes) {
      var node = this.nodes[id];
      if (node.type !== "materia") continue;
      var attrs = node.attrs;
      if (filters.category) {
        var cats = [attrs.category, slug(attrs.category_name || "")];
        if (cats.indexOf(slug(filters.category)) === -1) continue;
      }
      if (filters.element) {
        var els = (attrs.elements || []).map(slug);
        if (els.indexOf(slug(filters.element)) === -1) continue;
      }
      if (filters.location) {
        var locs = (attrs.found_at || []).map(slug);
        if (locs.indexOf(slug(filters.location)) === -1) continue;
      }
      if (filters.ability) {
        var abs = (attrs.abilities || []).map(slug);
        if (abs.indexOf(slug(filters.ability)) === -1) continue;
      }
      if (filters.text) {
        var hay = (node.label + " " + (attrs.notes || "")).toLowerCase();
        if (hay.indexOf(String(filters.text).toLowerCase()) === -1) continue;
      }
      out.push(node);
    }
    out.sort(function (a, b) { return a.label.toLowerCase() < b.label.toLowerCase() ? -1 : 1; });
    return out;
  };

  Graph.prototype.context = function (id) {
    var node = this.nodes[id];
    if (!node) return null;
    var groups = {};
    this.neighbors(id).forEach(function (hop) {
      var key = hop.rel + " " + (hop.direction === "out" ? "->" : "<-");
      var entry = { id: hop.node.id, label: hop.node.label, type: hop.node.type };
      if (hop.attrs && Object.keys(hop.attrs).length) entry.via = hop.attrs;
      (groups[key] = groups[key] || []).push(entry);
    });
    Object.keys(groups).forEach(function (key) {
      groups[key].sort(function (a, b) { return a.label.toLowerCase() < b.label.toLowerCase() ? -1 : 1; });
    });
    return { id: node.id, label: node.label, type: node.type, attrs: node.attrs, links: groups };
  };

  Graph.prototype.counts = function () {
    var byType = {}, byRel = {};
    for (var id in this.nodes) {
      var t = this.nodes[id].type;
      byType[t] = (byType[t] || 0) + 1;
    }
    this.edges.forEach(function (e) { byRel[e.rel] = (byRel[e.rel] || 0) + 1; });
    return { nodes: Object.keys(this.nodes).length, edges: this.edges.length,
             nodes_by_type: byType, edges_by_rel: byRel };
  };

  function buildGraph(data) {
    var graph = new Graph();
    var categoryNames = {}, categoryColors = {};
    (data.categories || []).forEach(function (c) {
      categoryNames[c.id] = c.name;
      categoryColors[c.id] = c.color || "";
      graph.addNode(nodeId("category", c.id), "category", c.name,
        { color: c.color || "", blurb: c.blurb || "" });
    });
    (data.elements || []).forEach(function (el) {
      graph.addNode(nodeId("element", el), "element", el, {});
    });
    (data.materia || []).forEach(function (m) {
      var mid = nodeId("materia", m.id);
      graph.addNode(mid, "materia", m.name, {
        category: m.category,
        category_name: categoryNames[m.category] || m.category,
        color: categoryColors[m.category] || "",
        elements: m.elements || [],
        abilities: m.abilities || [],
        found_at: m.found_at || [],
        notes: m.notes || ""
      });
      var catNode = nodeId("category", m.category);
      if (graph.nodes[catNode]) graph.addEdge(mid, "BELONGS_TO", catNode);
      (m.elements || []).forEach(function (el) {
        graph.addEdge(mid, "HAS_ELEMENT", graph.addNode(nodeId("element", el), "element", el, {}));
      });
      (m.abilities || []).forEach(function (ab) {
        graph.addEdge(mid, "GRANTS", graph.addNode(nodeId("ability", ab), "ability", ab, {}));
      });
      (m.found_at || []).forEach(function (loc) {
        graph.addEdge(mid, "FOUND_AT", graph.addNode(nodeId("location", loc), "location", loc, {}));
      });
    });
    (data.combos || []).forEach(function (combo) {
      var src = nodeId("materia", combo.support);
      var dst = nodeId("materia", combo.target);
      if (graph.nodes[src] && graph.nodes[dst]) {
        graph.addEdge(src, "PAIRS_WITH", dst, { slot: combo.slot || "", effect: combo.effect || "" });
      }
    });
    return graph;
  }

  root.FF7Graph = {
    slug: slug,
    nodeId: nodeId,
    Graph: Graph,
    buildGraph: buildGraph,
    ARROW: ARROW
  };
})(window);
