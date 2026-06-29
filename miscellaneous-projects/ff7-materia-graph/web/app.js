// DOM layer for the FF7 Materia Graph. This is the only file that touches the
// page; all the graph logic lives in graph-logic.js. Data comes from data.js
// (window.FF7_DATA), which the indexer generates from data/materia.json.

(function () {
  "use strict";

  var graph = FF7Graph.buildGraph(window.FF7_DATA);
  var meta = window.FF7_DATA.meta || {};

  var CATEGORY_HEX = {
    Green: getComputedStyle(document.documentElement).getPropertyValue("--c-magic").trim() || "#57c98a",
    Red: getComputedStyle(document.documentElement).getPropertyValue("--c-summon").trim() || "#e26277",
    Blue: getComputedStyle(document.documentElement).getPropertyValue("--c-support").trim() || "#5b93f2",
    Yellow: getComputedStyle(document.documentElement).getPropertyValue("--c-command").trim() || "#e4c452",
    Purple: getComputedStyle(document.documentElement).getPropertyValue("--c-independent").trim() || "#b681dd"
  };
  var TYPE_HEX = { element: "#3fc7b7", ability: "#93a3b6", location: "#7d8fb3", category: "#cdd7e3", materia: "#cdd7e3" };

  var state = { selected: null, category: "", element: "", text: "" };
  var visibleTypes = { materia: true, category: true, element: true, ability: true, location: true };
  var force = null;        // the full Map view
  var detailForce = null;  // the live mini graph in the Browse detail panel

  var els = {
    stats: document.getElementById("stats"),
    search: document.getElementById("search"),
    chips: document.getElementById("category-chips"),
    elementFilter: document.getElementById("element-filter"),
    listCount: document.getElementById("list-count"),
    list: document.getElementById("materia-list"),
    detail: document.getElementById("detail"),
    tabs: Array.prototype.slice.call(document.querySelectorAll(".tab")),
    browseView: document.getElementById("browse-view"),
    mapView: document.getElementById("map-view"),
    canvas: document.getElementById("graph-canvas"),
    typeToggles: document.getElementById("type-toggles"),
    legend: document.getElementById("legend"),
    mapReset: document.getElementById("map-reset"),
    mapClear: document.getElementById("map-clear")
  };

  function updateClearButtons() {
    if (els.mapClear) els.mapClear.disabled = !state.selected;
  }

  function esc(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function nodeColor(node) {
    if (node.type === "materia" || node.type === "category") {
      return CATEGORY_HEX[node.attrs.color] || TYPE_HEX[node.type];
    }
    return TYPE_HEX[node.type] || "#cdd7e3";
  }

  // -- controls -----------------------------------------------------------

  function buildControls() {
    var counts = graph.counts();
    els.stats.textContent = counts.nodes + " nodes and " + counts.edges +
      " edges built from " + counts.nodes_by_type.materia + " materia.";

    var categories = window.FF7_DATA.categories || [];
    var chipsHtml = ['<button class="chip active" data-category="">All</button>'];
    categories.forEach(function (c) {
      chipsHtml.push('<button class="chip" data-category="' + c.id + '">' + esc(c.name) + "</button>");
    });
    els.chips.innerHTML = chipsHtml.join("");

    var elementsHtml = ['<option value="">Any</option>'];
    (window.FF7_DATA.elements || []).forEach(function (e) {
      elementsHtml.push('<option value="' + esc(e) + '">' + esc(e) + "</option>");
    });
    els.elementFilter.innerHTML = elementsHtml.join("");
  }

  // -- list ---------------------------------------------------------------

  function renderList() {
    var results = graph.find({ category: state.category, element: state.element, text: state.text });
    els.listCount.textContent = results.length + (results.length === 1 ? " materia" : " materia");
    var html = results.map(function (node) {
      var active = node.id === state.selected ? " active" : "";
      return '<li class="' + active + '" data-id="' + node.id + '">' +
        '<span class="dot" style="background:' + nodeColor(node) + '"></span>' +
        '<span class="name">' + esc(node.label) + "</span>" +
        '<span class="cat">' + esc(node.attrs.category_name) + "</span></li>";
    }).join("");
    els.list.innerHTML = html || '<li class="empty">No materia match those filters.</li>';
  }

  // -- neighborhood graph (a live mini force graph in the detail panel) ----

  function egoCanvas() {
    return '<div class="graph-wrap"><canvas id="ego-canvas" class="ego-canvas"></canvas></div>';
  }

  function clearButtonHTML() {
    return '<button class="detail-clear" type="button" aria-label="Clear selection" title="Clear selection">&times;</button>';
  }

  function mountEgo(id) {
    if (detailForce) { detailForce.destroy(); detailForce = null; }
    var canvas = document.getElementById("ego-canvas");
    if (!canvas) return;
    detailForce = FF7Force.mount(canvas, graph, {
      centerId: id,
      pinCenter: true,
      idleAlpha: 0.03,
      labelAll: true,
      colorFor: nodeColor,
      selected: id,
      onSelect: function (other) { selectNode(other); }
    });
    detailForce.start();
  }

  // -- detail -------------------------------------------------------------

  function tagList(items, type) {
    return items.map(function (label) {
      var id = FF7Graph.nodeId(type, label);
      var clickable = graph.nodes[id] ? " link" : "";
      var data = graph.nodes[id] ? ' data-id="' + id + '"' : "";
      return '<span class="tag' + clickable + '"' + data + ">" + esc(label) + "</span>";
    }).join("");
  }

  function renderCombos(id) {
    var combos = graph.neighbors(id).filter(function (h) { return h.rel === "PAIRS_WITH"; });
    if (!combos.length) return "";
    var self = graph.nodes[id].label;
    var rows = combos.map(function (h) {
      var other = h.node.label;
      var pair = h.direction === "out" ? self + " + " + other : other + " + " + self;
      pair = esc(pair).replace(esc(other),
        '<span class="other" data-id="' + h.node.id + '">' + esc(other) + "</span>");
      return '<div class="combo"><div class="pair">' + pair + "</div>" +
        '<div class="effect">' + esc(h.attrs.effect || "") + "</div></div>";
    }).join("");
    return '<div class="field"><div class="field-label">Combos</div>' + rows + "</div>";
  }

  function renderMateriaDetail(node) {
    var a = node.attrs;
    var html = '<div class="detail-head">' +
      '<span class="dot" style="background:' + nodeColor(node) + '"></span>' +
      "<h2>" + esc(node.label) + "</h2>" +
      '<span class="category">' + esc(a.category_name) + " materia</span>" +
      clearButtonHTML() + "</div>";
    if (a.notes) html += '<p class="notes">' + esc(a.notes) + "</p>";
    html += egoCanvas();
    if (a.elements && a.elements.length) {
      html += '<div class="field"><div class="field-label">Element</div><div class="tags">' +
        tagList(a.elements, "element") + "</div></div>";
    }
    if (a.abilities && a.abilities.length) {
      html += '<div class="field"><div class="field-label">Grants</div><div class="tags">' +
        a.abilities.map(function (ab) { return '<span class="tag">' + esc(ab) + "</span>"; }).join("") +
        "</div></div>";
    }
    html += '<div class="field"><div class="field-label">Found at</div><div class="tags">' +
      tagList(a.found_at || [], "location") + "</div></div>";
    html += renderCombos(node.id);
    return html;
  }

  function renderOtherDetail(node) {
    var connected = graph.neighbors(node.id)
      .filter(function (h) { return h.node.type === "materia"; })
      .map(function (h) { return h.node; });
    connected.sort(function (x, y) { return x.label.toLowerCase() < y.label.toLowerCase() ? -1 : 1; });
    var html = '<div class="detail-head">' +
      '<span class="dot" style="background:' + nodeColor(node) + '"></span>' +
      "<h2>" + esc(node.label) + "</h2>" +
      '<span class="category">' + esc(node.type) + "</span>" +
      clearButtonHTML() + "</div>";
    html += '<p class="notes">' + connected.length + " materia connect to this " + esc(node.type) + ".</p>";
    html += egoCanvas();
    html += '<div class="field"><div class="field-label">Connected materia</div><div class="tags">' +
      connected.map(function (m) {
        return '<span class="tag link" data-id="' + m.id + '">' + esc(m.label) + "</span>";
      }).join("") + "</div></div>";
    return html;
  }

  function selectNode(id) {
    if (!graph.nodes[id]) return;
    state.selected = id;
    var node = graph.nodes[id];
    els.detail.innerHTML = node.type === "materia" ? renderMateriaDetail(node) : renderOtherDetail(node);
    renderList();
    mountEgo(id);
    updateClearButtons();
    if (force) force.setSelected(id);
    els.detail.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // -- map view -----------------------------------------------------------

  function buildMap() {
    var types = [["materia", "Materia"], ["category", "Category"], ["element", "Element"],
      ["ability", "Ability"], ["location", "Location"]];
    els.typeToggles.innerHTML = types.map(function (t) {
      return '<label><input type="checkbox" value="' + t[0] + '" checked> ' + t[1] + "</label>";
    }).join("");

    var legend = [
      ["Magic", CATEGORY_HEX.Green], ["Summon", CATEGORY_HEX.Red], ["Support", CATEGORY_HEX.Blue],
      ["Command", CATEGORY_HEX.Yellow], ["Independent", CATEGORY_HEX.Purple],
      ["Element", TYPE_HEX.element], ["Ability", TYPE_HEX.ability], ["Location", TYPE_HEX.location]
    ];
    els.legend.innerHTML = legend.map(function (l) {
      return '<span><span class="dot" style="background:' + l[1] + '"></span>' + l[0] + "</span>";
    }).join("");

    els.typeToggles.addEventListener("change", function () {
      visibleTypes = {};
      els.typeToggles.querySelectorAll("input").forEach(function (cb) { visibleTypes[cb.value] = cb.checked; });
      if (force) force.setVisibleTypes(visibleTypes);
    });
    els.mapReset.addEventListener("click", function () { if (force) force.reset(); });
    els.mapClear.addEventListener("click", clearSelection);
  }

  function clearSelection() {
    state.selected = null;
    if (detailForce) { detailForce.destroy(); detailForce = null; }
    els.detail.innerHTML = '<p class="empty">Select a materia to explore its connections.</p>';
    if (force) force.setSelected(null);
    renderList();
    updateClearButtons();
  }

  function switchView(view) {
    var browse = view === "browse";
    els.browseView.hidden = !browse;
    els.mapView.hidden = browse;
    els.tabs.forEach(function (t) { t.classList.toggle("active", t.getAttribute("data-view") === view); });
    if (view === "map") {
      if (!force) {
        force = FF7Force.mount(els.canvas, graph, {
          colorFor: nodeColor,
          selected: state.selected,
          visibleTypes: visibleTypes,
          onSelect: function (id) { switchView("browse"); selectNode(id); }
        });
        force.start();
      } else {
        force.setSelected(state.selected);
        force.onShow();
      }
    }
  }

  // -- events -------------------------------------------------------------

  function onClickId(container, handler) {
    container.addEventListener("click", function (event) {
      var target = event.target.closest("[data-id]");
      if (target && container.contains(target)) handler(target.getAttribute("data-id"));
    });
  }

  function wireEvents() {
    els.search.addEventListener("input", function () {
      state.text = els.search.value.trim();
      renderList();
    });
    els.chips.addEventListener("click", function (event) {
      var btn = event.target.closest(".chip");
      if (!btn) return;
      state.category = btn.getAttribute("data-category");
      Array.prototype.forEach.call(els.chips.children, function (c) { c.classList.remove("active"); });
      btn.classList.add("active");
      renderList();
    });
    els.elementFilter.addEventListener("change", function () {
      state.element = els.elementFilter.value;
      renderList();
    });
    onClickId(els.list, selectNode);
    onClickId(els.detail, selectNode);
    els.detail.addEventListener("click", function (event) {
      if (event.target.closest(".detail-clear")) clearSelection();
    });
    els.tabs.forEach(function (t) {
      t.addEventListener("click", function () { switchView(t.getAttribute("data-view")); });
    });
  }

  // -- start --------------------------------------------------------------

  buildControls();
  buildMap();
  wireEvents();
  renderList();
  updateClearButtons();
})();
