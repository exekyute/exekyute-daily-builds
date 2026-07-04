/* Page wiring for the grant compliance view.
 *
 * Renders the drawdown timeline as an SVG chart with the award budget rule and a
 * run-rate projection, a budget-versus-actual bar for each cost category, and the
 * reporting deadlines with their status. It reads the embedded sample on open and
 * can import a fresh timeline.csv. The arithmetic and parsing live in timeline.js.
 */
(function () {
  "use strict";

  var T = window.GrantTimeline;
  var GEOM = { left: 78, top: 24, width: 640, height: 296, fullWidth: 760, fullHeight: 380 };

  function money(v) { return T.formatMoney(v); }

  function svgLine(points, cls) {
    return '<polyline class="' + cls + '" points="' + points + '" fill="none" />';
  }

  function buildSvg(rows, award) {
    var series = T.buildSeries(rows, award);
    var geom = { left: GEOM.left, top: GEOM.top, width: GEOM.width, height: GEOM.height, maxVal: series.maxVal };
    var parts = [];

    for (var q = 0; q <= 4; q++) {
      var val = series.maxVal * q / 4;
      var y = geom.top + geom.height - (geom.height * q / 4);
      parts.push('<line class="grid" x1="' + geom.left + '" y1="' + y + '" x2="' + (geom.left + geom.width) + '" y2="' + y + '" />');
      parts.push('<text class="axis-y" x="' + (geom.left - 10) + '" y="' + (y + 4) + '">' + money(val) + '</text>');
    }

    var ay = geom.top + geom.height - (geom.height * award / series.maxVal);
    parts.push('<line class="budget-rule" x1="' + geom.left + '" y1="' + ay + '" x2="' + (geom.left + geom.width) + '" y2="' + ay + '" />');
    parts.push('<text class="budget-label" x="' + (geom.left + geom.width) + '" y="' + (ay - 6) + '">Award ' + money(award) + '</text>');

    parts.push(svgLine(T.pointsFor(series.projected, geom), "line-projected"));
    parts.push(svgLine(T.pointsFor(series.actual, geom), "line-actual"));

    rows.forEach(function (r, i) {
      var x = geom.left + (series.periods.length === 1 ? 0 : (geom.width * i) / (series.periods.length - 1));
      var yActual = geom.top + geom.height - (geom.height * r.cumulative_allowable / series.maxVal);
      var yProjected = geom.top + geom.height - (geom.height * r.projected_total / series.maxVal);
      parts.push('<circle class="dot ' + T.statusClass(r.status) + '" cx="' + Math.round(x) + '" cy="' + Math.round(yProjected) + '" r="5" />');
      parts.push('<circle class="dot actual" cx="' + Math.round(x) + '" cy="' + Math.round(yActual) + '" r="4" />');
      parts.push('<text class="axis-x" x="' + Math.round(x) + '" y="' + (geom.top + geom.height + 22) + '">P' + r.period + '</text>');
    });

    return '<svg viewBox="0 0 ' + GEOM.fullWidth + ' ' + GEOM.fullHeight + '" role="img" aria-label="Grant drawdown and run-rate projection against the award">' +
      parts.join("") + '</svg>';
  }

  function buildSummary(rows) {
    var s = T.finalSummary(rows);
    var cards = [
      ["Allowable drawn", money(s.allowable), ""],
      ["Disallowed", money(s.disallowed), s.disallowed > 0 ? "over-budget" : ""],
      ["Remaining", money(s.remaining), ""],
      ["Projected at award end", money(s.projected), T.statusClass(s.status)],
      ["Reports overdue", String(s.overdue), s.overdue > 0 ? "over-budget" : "on-track"],
    ];
    return cards.map(function (c) {
      return '<div class="card"><span class="card-label">' + c[0] + '</span>' +
        '<span class="card-value ' + c[2] + '">' + c[1] + '</span></div>';
    }).join("");
  }

  function buildCategories(categories) {
    var maxBudget = Math.max.apply(null, categories.map(function (c) { return c.budget; }));
    var rows = categories.map(function (c) {
      var budgetWidth = Math.round((c.budget / maxBudget) * 100);
      var spentWidth = Math.round((c.spent / maxBudget) * 100);
      var over = c.status === "Over budget";
      return '<div class="cat-row"><div class="cat-name">' + c.category + '</div>' +
        '<div class="cat-bar" style="width:' + budgetWidth + '%">' +
        '<div class="cat-fill ' + (over ? "over" : "") + '" style="width:' + (budgetWidth ? Math.round((spentWidth / budgetWidth) * 100) : 0) + '%"></div></div>' +
        '<div class="cat-amounts">' + money(c.spent) + ' of ' + money(c.budget) + '</div></div>';
    }).join("");
    return rows;
  }

  function buildDeadlines(deadlines) {
    return deadlines.map(function (d) {
      return '<li><span class="deadline-name">' + d.report + '</span>' +
        '<span class="deadline-due">due period ' + d.due_period + '</span>' +
        '<span class="pill ' + T.statusClass(d.status) + '">' + d.status + '</span></li>';
    }).join("");
  }

  function render(payload) {
    document.getElementById("summary").innerHTML = buildSummary(payload.timeline);
    document.getElementById("chart").innerHTML = buildSvg(payload.timeline, payload.awardTotal);
    if (payload.categories) { document.getElementById("categories").innerHTML = buildCategories(payload.categories); }
    if (payload.deadlines) { document.getElementById("deadlines").innerHTML = buildDeadlines(payload.deadlines); }
  }

  function importTimeline(file) {
    var reader = new FileReader();
    reader.onload = function () {
      var rows = T.parseTimelineCSV(String(reader.result));
      if (!rows.length) { return; }
      var award = window.GRANT_SAMPLE.awardTotal;
      render({ awardTotal: award, timeline: rows, categories: null, deadlines: null });
      document.getElementById("note").textContent = "Loaded " + rows.length + " periods from file.";
    };
    reader.readAsText(file);
  }

  document.addEventListener("DOMContentLoaded", function () {
    render(window.GRANT_SAMPLE);
    document.getElementById("import").addEventListener("change", function (e) {
      if (e.target.files && e.target.files[0]) { importTimeline(e.target.files[0]); e.target.value = ""; }
    });
    document.getElementById("reset").addEventListener("click", function () {
      render(window.GRANT_SAMPLE);
      document.getElementById("note").textContent = "Reset to the sample grant.";
    });
  });
})();
