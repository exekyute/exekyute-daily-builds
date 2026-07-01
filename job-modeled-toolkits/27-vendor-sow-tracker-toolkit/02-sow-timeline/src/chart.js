/* Page wiring for the SOW timeline view.
 *
 * Renders the earned-value timeline as an SVG burn chart with a budget rule,
 * a per-week table, a milestone table, and summary cards. It reads the embedded
 * sample on open and can import a fresh timeline.csv. All arithmetic and parsing
 * live in timeline.js; this file only builds the page from those results.
 */
(function () {
  "use strict";

  var T = window.SowTimeline;
  var GEOM = { left: 72, top: 24, width: 648, height: 300, fullWidth: 760, fullHeight: 384, bottom: 44 };

  function money(v) { return T.formatMoney(v); }

  function budgetFromTimeline(rows) {
    for (var i = rows.length - 1; i >= 0; i--) {
      if (rows[i].percent_complete > 0) {
        return Math.round(rows[i].earned_value / rows[i].percent_complete);
      }
    }
    return Math.max.apply(null, rows.map(function (r) { return r.earned_value; }));
  }

  function svgLine(points, cls) {
    return '<polyline class="' + cls + '" points="' + points + '" fill="none" />';
  }

  function buildSvg(rows, budget) {
    var series = T.buildSeries(rows, budget);
    var geom = { left: GEOM.left, top: GEOM.top, width: GEOM.width, height: GEOM.height, maxVal: series.maxVal };
    var parts = [];

    // Horizontal gridlines and y labels at quarters of the scale.
    for (var q = 0; q <= 4; q++) {
      var val = series.maxVal * q / 4;
      var y = geom.top + geom.height - (geom.height * q / 4);
      parts.push('<line class="grid" x1="' + geom.left + '" y1="' + y + '" x2="' + (geom.left + geom.width) + '" y2="' + y + '" />');
      parts.push('<text class="axis-y" x="' + (geom.left - 10) + '" y="' + (y + 4) + '">' + money(val) + '</text>');
    }

    // Budget rule.
    var by = geom.top + geom.height - (geom.height * budget / series.maxVal);
    parts.push('<line class="budget-rule" x1="' + geom.left + '" y1="' + by + '" x2="' + (geom.left + geom.width) + '" y2="' + by + '" />');
    parts.push('<text class="budget-label" x="' + (geom.left + geom.width) + '" y="' + (by - 6) + '">Budget ' + money(budget) + '</text>');

    // Cost and earned lines.
    parts.push(svgLine(T.pointsFor(series.cost, geom), "line-cost"));
    parts.push(svgLine(T.pointsFor(series.earned, geom), "line-earned"));

    // Week markers and x labels, with the cost point colored by status.
    rows.forEach(function (r, i) {
      var x = geom.left + (series.weeks.length === 1 ? 0 : (geom.width * i) / (series.weeks.length - 1));
      var yCost = geom.top + geom.height - (geom.height * r.cost_to_date / series.maxVal);
      var yEarned = geom.top + geom.height - (geom.height * r.earned_value / series.maxVal);
      parts.push('<circle class="dot earned" cx="' + Math.round(x) + '" cy="' + Math.round(yEarned) + '" r="4" />');
      parts.push('<circle class="dot ' + T.statusClass(r.status) + '" cx="' + Math.round(x) + '" cy="' + Math.round(yCost) + '" r="5" />');
      parts.push('<text class="axis-x" x="' + Math.round(x) + '" y="' + (geom.top + geom.height + 22) + '">Week ' + r.week + '</text>');
    });

    return '<svg viewBox="0 0 ' + GEOM.fullWidth + ' ' + GEOM.fullHeight + '" role="img" aria-label="Cost and earned value by week against budget">' +
      parts.join("") + '</svg>';
  }

  function buildSummary(rows, budget) {
    var s = T.finalSummary(rows);
    var cards = [
      ["Total budget", money(budget), ""],
      ["Estimate at completion", money(s.eac), T.statusClass(s.status)],
      ["Variance at completion", money(s.vac), s.vac < 0 ? "over-budget" : "on-track"],
      ["Holdback released", money(s.holdbackReleased), ""],
      ["Status", s.status, T.statusClass(s.status)],
    ];
    return cards.map(function (c) {
      return '<div class="card"><span class="card-label">' + c[0] + '</span>' +
        '<span class="card-value ' + c[2] + '">' + c[1] + '</span></div>';
    }).join("");
  }

  function buildWeekTable(rows) {
    var body = rows.map(function (r) {
      return "<tr><td>Week " + r.week + "</td><td class='num'>" + money(r.cost_to_date) +
        "</td><td class='num'>" + money(r.earned_value) + "</td><td class='num'>" + r.cpi.toFixed(4) +
        "</td><td class='num'>" + money(r.eac) + "</td><td class='num'>" + money(r.vac) +
        "</td><td><span class='pill " + T.statusClass(r.status) + "'>" + r.status + "</span></td></tr>";
    }).join("");
    return "<table class='data'><thead><tr><th>Period</th><th>Cost to date</th><th>Earned</th>" +
      "<th>CPI</th><th>EAC</th><th>VAC</th><th>Status</th></tr></thead><tbody>" + body + "</tbody></table>";
  }

  function buildMilestoneTable(milestones) {
    if (!milestones || !milestones.length) { return ""; }
    var body = milestones.map(function (m) {
      return "<tr><td>" + m.milestone_id + "</td><td>" + m.name + "</td><td class='num'>" + money(m.budget) +
        "</td><td class='num'>" + money(m.actual_cost) + "</td><td class='num'>" + money(m.variance) +
        "</td><td><span class='pill " + T.statusClass(m.status) + "'>" + m.status + "</span></td></tr>";
    }).join("");
    return "<h2>Milestones</h2><table class='data'><thead><tr><th>ID</th><th>Milestone</th><th>Budget</th>" +
      "<th>Actual</th><th>Variance</th><th>Status</th></tr></thead><tbody>" + body + "</tbody></table>";
  }

  function render(payload) {
    var budget = payload.totalBudget != null ? payload.totalBudget : budgetFromTimeline(payload.timeline);
    document.getElementById("summary").innerHTML = buildSummary(payload.timeline, budget);
    document.getElementById("chart").innerHTML = buildSvg(payload.timeline, budget);
    document.getElementById("weeks").innerHTML = buildWeekTable(payload.timeline);
    document.getElementById("milestones").innerHTML = buildMilestoneTable(payload.milestones);
  }

  function importTimeline(file) {
    var reader = new FileReader();
    reader.onload = function () {
      var rows = T.parseTimelineCSV(String(reader.result));
      if (!rows.length) { return; }
      render({ totalBudget: budgetFromTimeline(rows), timeline: rows, milestones: null });
      var note = document.getElementById("note");
      note.textContent = "Loaded " + rows.length + " weeks from file.";
    };
    reader.readAsText(file);
  }

  document.addEventListener("DOMContentLoaded", function () {
    render(window.SOW_SAMPLE);
    document.getElementById("import").addEventListener("change", function (e) {
      if (e.target.files && e.target.files[0]) { importTimeline(e.target.files[0]); e.target.value = ""; }
    });
    document.getElementById("reset").addEventListener("click", function () {
      render(window.SOW_SAMPLE);
      document.getElementById("note").textContent = "Reset to the sample SOW.";
    });
  });
})();
