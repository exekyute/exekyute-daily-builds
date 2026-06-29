// Force-directed graph drawn on a canvas with plain JavaScript. A small physics
// loop pushes nodes apart, pulls linked nodes together, and nudges everything
// toward the center until it settles. No libraries, so the page still opens by
// double-clicking.
//
// Two modes, both through mount():
//   - Full map: every visible node (the Map tab).
//   - Ego graph: one center node plus its direct neighbors (the Browse detail),
//     with the center pinned and a little perpetual motion so it feels alive.
//
// Attached to window.FF7Force.

(function (root) {
  "use strict";

  function mount(canvas, graph, opts) {
    opts = opts || {};
    var ctx = canvas.getContext("2d");
    var DPR = window.devicePixelRatio || 1;
    var colorFor = opts.colorFor || function () { return "#cdd7e3"; };
    var onSelect = opts.onSelect || function () {};
    var centerId = opts.centerId || null;
    var pinCenter = !!opts.pinCenter;
    var labelAll = !!opts.labelAll;
    var idleAlpha = opts.idleAlpha || 0;          // a floor so motion never fully stops
    var ego = !!centerId;

    var W = 0, H = 0;
    var nodes = [], index = {}, links = [];
    var visibleTypes = opts.visibleTypes ||
      { materia: true, category: true, element: true, ability: true, location: true };
    var transform = { scale: 1, x: 0, y: 0 };
    var hovered = null, selected = opts.selected || null;
    var dragging = null, panning = false, moved = false, lastX = 0, lastY = 0;
    var alpha = 0, running = false, rafId = null, entryAlpha = 0;

    // -- sizing -----------------------------------------------------------

    function resize() {
      var rect = canvas.getBoundingClientRect();
      // Fall back to a sane size if the element has not been laid out yet (some
      // embedded previews report a zero-size viewport until they paint).
      W = rect.width > 20 ? rect.width : 900;
      H = rect.height > 20 ? rect.height : (ego ? 340 : 560);
      canvas.width = W * DPR;
      canvas.height = H * DPR;
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    }

    // -- build particles --------------------------------------------------

    function build() {
      nodes = [];
      index = {};
      links = [];
      var degree = {};
      graph.edges.forEach(function (e) {
        degree[e.src] = (degree[e.src] || 0) + 1;
        degree[e.dst] = (degree[e.dst] || 0) + 1;
      });

      var ids;
      if (ego && graph.nodes[centerId]) {
        var keep = {};
        keep[centerId] = true;
        graph.neighbors(centerId).forEach(function (h) { keep[h.node.id] = true; });
        ids = Object.keys(keep);
      } else {
        ids = Object.keys(graph.nodes).filter(function (id) {
          return visibleTypes[graph.nodes[id].type];
        });
      }

      var cx = W / 2, cy = H / 2, R = Math.min(W, H) * (ego ? 0.34 : 0.42);
      ids.forEach(function (id, i) {
        var n = graph.nodes[id];
        var isCenter = id === centerId;
        var ang = (2 * Math.PI * i) / ids.length;
        var node = {
          id: id, type: n.type, label: n.label, attrs: n.attrs,
          x: isCenter ? cx : cx + R * Math.cos(ang) + (i % 7 - 3),
          y: isCenter ? cy : cy + R * Math.sin(ang) + (i % 5 - 2),
          vx: 0, vy: 0, deg: degree[id] || 0,
          fixed: isCenter && pinCenter, center: isCenter
        };
        node.r = isCenter ? 11 : 3.5 + Math.sqrt(node.deg) * 1.4;
        nodes.push(node);
        index[id] = node;
      });
      graph.edges.forEach(function (e) {
        if (index[e.src] && index[e.dst]) links.push({ s: index[e.src], t: index[e.dst], rel: e.rel });
      });

      if (ego) {
        // A short warmup, then a low resting energy keeps the ego graph alive.
        alpha = 1;
        for (var k = 0; k < 55; k++) step();
        alpha = Math.max(idleAlpha, 0.5);
      } else {
        // Settle the map fully to find its final shape, snapshotting a partly
        // settled state partway through. We fit the camera to the FINAL shape,
        // then rewind the nodes to the snapshot. reheat() replays the rest of the
        // settle as an entrance animation that lands exactly inside the fixed
        // frame, so the nodes move but the camera never resizes.
        alpha = 1;
        var snapped = false;
        for (var s = 0; s < 1000 && alpha > 0.01; s++) {
          step();
          if (!snapped && alpha <= 0.75) {
            snapped = true;
            entryAlpha = alpha;
            nodes.forEach(function (n) { n.ex = n.x; n.ey = n.y; n.evx = n.vx; n.evy = n.vy; });
          }
        }
        fitView();
        if (snapped) {
          nodes.forEach(function (n) { n.x = n.ex; n.y = n.ey; n.vx = n.evx; n.vy = n.evy; });
          alpha = entryAlpha;
        } else {
          alpha = 0;
        }
      }
    }

    // -- physics ----------------------------------------------------------

    function step() {
      var cx = W / 2, cy = H / 2;
      var REP = ego ? 3000 : 8200;
      var SPRING = ego ? 0.06 : 0.045;
      var LEN = ego ? 84 : 72;
      // Weaker horizontal pull and stronger vertical pull spread the full map
      // into a wide, sideways oval instead of a crowded circle.
      var GRAVX = ego ? 0.02 : 0.009;
      var GRAVY = ego ? 0.02 : 0.05;
      var DAMP = 0.85, MAX = 20;
      var i, j, a, b, dx, dy, d2, d, f, ux, uy;

      for (i = 0; i < nodes.length; i++) {
        a = nodes[i];
        for (j = i + 1; j < nodes.length; j++) {
          b = nodes[j];
          dx = a.x - b.x; dy = a.y - b.y;
          d2 = dx * dx + dy * dy;
          if (d2 < 0.01) { dx = Math.cos(i + j); dy = Math.sin(i + j); d2 = 0.01; }
          d = Math.sqrt(d2);
          f = (REP / d2) * alpha;
          ux = dx / d; uy = dy / d;
          a.vx += f * ux; a.vy += f * uy;
          b.vx -= f * ux; b.vy -= f * uy;
        }
      }

      links.forEach(function (e) {
        dx = e.t.x - e.s.x; dy = e.t.y - e.s.y;
        d = Math.sqrt(dx * dx + dy * dy) + 0.01;
        f = (d - LEN) * SPRING * alpha;
        ux = dx / d; uy = dy / d;
        e.s.vx += f * ux; e.s.vy += f * uy;
        e.t.vx -= f * ux; e.t.vy -= f * uy;
      });

      nodes.forEach(function (n) {
        if (n.fixed) { n.vx = 0; n.vy = 0; n.x = cx; n.y = cy; return; }
        n.vx += (cx - n.x) * GRAVX * alpha;
        n.vy += (cy - n.y) * GRAVY * alpha;
        n.vx *= DAMP; n.vy *= DAMP;
        if (n.vx > MAX) n.vx = MAX; if (n.vx < -MAX) n.vx = -MAX;
        if (n.vy > MAX) n.vy = MAX; if (n.vy < -MAX) n.vy = -MAX;
        n.x += n.vx; n.y += n.vy;
      });

      alpha *= 0.985;
      if (alpha < idleAlpha) alpha = idleAlpha;
    }

    // -- drawing ----------------------------------------------------------

    function neighborsOf(node) {
      if (!node) return null;
      var set = {};
      links.forEach(function (e) {
        if (e.s === node) set[e.t.id] = true;
        if (e.t === node) set[e.s.id] = true;
      });
      return set;
    }

    function draw() {
      ctx.clearRect(0, 0, W, H);
      ctx.save();
      ctx.translate(transform.x, transform.y);
      ctx.scale(transform.scale, transform.scale);

      var focus = hovered || (selected && index[selected]) || null;
      var near = neighborsOf(focus);
      var s = transform.scale;

      links.forEach(function (e) {
        var active = focus && (e.s === focus || e.t === focus);
        ctx.strokeStyle = active ? "rgba(63,199,183,0.6)"
          : focus ? "rgba(120,135,155,0.07)" : "rgba(120,135,155,0.18)";
        ctx.lineWidth = (active ? 1.6 : 0.8) / s;
        ctx.beginPath();
        ctx.moveTo(e.s.x, e.s.y);
        ctx.lineTo(e.t.x, e.t.y);
        ctx.stroke();
      });

      nodes.forEach(function (n) {
        var dim = focus && n !== focus && !(near && near[n.id]);
        ctx.globalAlpha = dim ? 0.25 : 1;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, 2 * Math.PI);
        ctx.fillStyle = colorFor(n);
        ctx.fill();
        if (n.center || n === focus || (selected && n.id === selected)) {
          ctx.lineWidth = 2 / s;
          ctx.strokeStyle = "#e7eef6";
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
      });

      ctx.fillStyle = "#e7eef6";
      ctx.textAlign = "center";
      nodes.forEach(function (n) {
        var show = labelAll || n.type === "category" || n.center || n === focus ||
          (selected && n.id === selected) || (near && near[n.id]);
        if (!show) return;
        var size = (n.center || n.type === "category" ? 12.5 : 11) / s;
        ctx.font = (n.center || n.type === "category" ? "bold " : "") + size + "px 'Segoe UI', system-ui, sans-serif";
        ctx.fillText(n.label, n.x, n.y - n.r - 5 / s);
      });

      ctx.restore();
    }

    // Center and zoom the view so the whole layout fits the canvas with a margin.
    function fitView() {
      if (!nodes.length) { transform = { scale: 1, x: 0, y: 0 }; return; }
      var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      nodes.forEach(function (n) {
        if (n.x - n.r < minX) minX = n.x - n.r;
        if (n.x + n.r > maxX) maxX = n.x + n.r;
        if (n.y - n.r < minY) minY = n.y - n.r;
        if (n.y + n.r > maxY) maxY = n.y + n.r;
      });
      var pad = 48;
      var bw = (maxX - minX) || 1, bh = (maxY - minY) || 1;
      var scale = Math.min((W - 2 * pad) / bw, (H - 2 * pad) / bh, 1.6);
      scale = Math.max(scale, 0.15);
      transform = {
        scale: scale,
        x: (W - scale * (minX + maxX)) / 2,
        y: (H - scale * (minY + maxY)) / 2
      };
    }

    // -- loop -------------------------------------------------------------

    function tick() {
      step();
      draw();
      if (alpha > 0.01 || dragging) {
        rafId = requestAnimationFrame(tick);
      } else {
        running = false;
        draw();
      }
    }

    function ensureRunning() {
      if (!running) { running = true; rafId = requestAnimationFrame(tick); }
    }

    function reheat(value) {
      alpha = Math.max(alpha, value || 0.5);
      ensureRunning();
    }

    // -- interaction ------------------------------------------------------

    function toWorld(ev) {
      var rect = canvas.getBoundingClientRect();
      var sx = ev.clientX - rect.left;
      var sy = ev.clientY - rect.top;
      return { x: (sx - transform.x) / transform.scale, y: (sy - transform.y) / transform.scale };
    }

    function nodeAt(p) {
      for (var i = nodes.length - 1; i >= 0; i--) {
        var n = nodes[i];
        var dx = n.x - p.x, dy = n.y - p.y;
        var hit = n.r + 4;
        if (dx * dx + dy * dy <= hit * hit) return n;
      }
      return null;
    }

    function onMove(ev) {
      var p = toWorld(ev);
      if (dragging) {
        dragging.x = p.x; dragging.y = p.y; dragging.vx = 0; dragging.vy = 0;
        moved = true; reheat(0.4); return;
      }
      if (panning) {
        transform.x += ev.clientX - lastX;
        transform.y += ev.clientY - lastY;
        lastX = ev.clientX; lastY = ev.clientY;
        if (!running) draw();
        return;
      }
      var n = nodeAt(p);
      if (n !== hovered) {
        hovered = n;
        canvas.style.cursor = n ? "pointer" : (ego ? "default" : "grab");
        if (!running) draw();
      }
    }

    function onDown(ev) {
      var p = toWorld(ev);
      var n = nodeAt(p);
      moved = false;
      if (n) { dragging = n; if (!n.center) n.fixed = true; reheat(0.5); }
      else if (!ego) { panning = true; lastX = ev.clientX; lastY = ev.clientY; canvas.style.cursor = "grabbing"; }
    }

    function onUp() {
      if (dragging) {
        var d = dragging;
        if (!d.center) d.fixed = false;
        dragging = null;
        if (!moved && !d.center) onSelect(d.id);
        reheat(0.3);
      }
      panning = false;
      canvas.style.cursor = hovered ? "pointer" : (ego ? "default" : "grab");
    }

    function onWheel(ev) {
      if (ego) return;
      ev.preventDefault();
      var rect = canvas.getBoundingClientRect();
      var p = toWorld(ev);
      var factor = ev.deltaY < 0 ? 1.12 : 0.89;
      var ns = Math.min(4, Math.max(0.2, transform.scale * factor));
      transform.x = (ev.clientX - rect.left) - p.x * ns;
      transform.y = (ev.clientY - rect.top) - p.y * ns;
      transform.scale = ns;
      if (!running) draw();
    }

    function onResize() {
      if (!canvas.offsetParent) return;
      resize();
      if (!ego) fitView();
      if (!running) draw();
    }

    canvas.addEventListener("mousemove", onMove);
    canvas.addEventListener("mousedown", onDown);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("mouseup", onUp);
    window.addEventListener("resize", onResize);

    // -- public API -------------------------------------------------------

    return {
      // build() pre-settles the layout, so a single synchronous draw shows a
      // good frame right away. reheat() then animates it in browsers that run
      // requestAnimationFrame.
      // build() fits the camera (map) and leaves the layout primed for an entrance
      // animation, so start just paints the first frame and runs the loop.
      start: function () { resize(); build(); if (ego) { transform = { scale: 1, x: 0, y: 0 }; } draw(); if (ego) { reheat(0.5); } else { ensureRunning(); } },
      setVisibleTypes: function (v) { visibleTypes = v; build(); draw(); ensureRunning(); },
      setSelected: function (id) { selected = id; draw(); },
      reset: function () { if (ego) { transform = { scale: 1, x: 0, y: 0 }; } else { fitView(); } draw(); },
      // Called when the tab becomes visible again. Only re-fits if the canvas
      // actually changed size (e.g. the window was resized while hidden), so a
      // plain tab toggle never moves or rescales the layout.
      onShow: function () {
        var ow = W, oh = H;
        resize();
        if (Math.abs(W - ow) > 1 || Math.abs(H - oh) > 1) fitView();
        draw();
      },
      reheat: reheat,
      destroy: function () {
        running = false;
        if (rafId) cancelAnimationFrame(rafId);
        canvas.removeEventListener("mousemove", onMove);
        canvas.removeEventListener("mousedown", onDown);
        canvas.removeEventListener("wheel", onWheel);
        window.removeEventListener("mouseup", onUp);
        window.removeEventListener("resize", onResize);
      }
    };
  }

  root.FF7Force = { mount: mount };
})(window);
