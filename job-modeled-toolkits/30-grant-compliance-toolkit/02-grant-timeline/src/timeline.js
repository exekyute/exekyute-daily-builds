/* Timeline logic for the grant compliance view.
 *
 * Pure functions: parse the engine's timeline CSV, build the chart series, and
 * format values, with no DOM access. The chart wiring in chart.js calls these and
 * the test harness in tests.js checks them. The figures match the Python engine
 * in 01 to the cent.
 *
 * Runs in the browser (attaches GrantTimeline to the window) and under Node (it
 * exports the same object), so the tests run in either place.
 */
(function (global) {
  "use strict";

  var TIMELINE_NUMERIC = ["period", "cumulative_allowable", "cumulative_disallowed",
    "burn_rate", "remaining", "projected_total", "projected_variance", "reports_overdue"];

  function parseRows(text, numericFields) {
    var lines = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n")
      .filter(function (l) { return l.trim() !== ""; });
    var headers = lines[0].split(",");
    return lines.slice(1).map(function (line) {
      var cells = line.split(",");
      var row = {};
      headers.forEach(function (h, i) {
        var key = h.trim();
        var value = (cells[i] || "").trim();
        row[key] = numericFields.indexOf(key) !== -1 ? Number(value) : value;
      });
      return row;
    });
  }

  function parseTimelineCSV(text) { return parseRows(text, TIMELINE_NUMERIC); }

  function formatMoney(value) {
    return Number(value).toLocaleString("en-CA", { style: "currency", currency: "CAD" });
  }

  function statusClass(status) {
    if (status === "Over budget" || status === "Overdue") { return "over-budget"; }
    if (status === "Due now" || status === "Upcoming") { return "at-risk"; }
    return "on-track";
  }

  // Build the drawdown chart series: the actual cumulative spend, the run-rate
  // projection, and the award budget rule. maxVal fits all three.
  function buildSeries(rows, award) {
    var periods = rows.map(function (r) { return r.period; });
    var actual = rows.map(function (r) { return r.cumulative_allowable; });
    var projected = rows.map(function (r) { return r.projected_total; });
    var maxVal = Math.max(award, Math.max.apply(null, projected), Math.max.apply(null, actual));
    return { periods: periods, actual: actual, projected: projected, award: award, maxVal: maxVal };
  }

  function pointsFor(values, geom) {
    var n = values.length;
    return values.map(function (v, i) {
      var x = geom.left + (n === 1 ? 0 : (geom.width * i) / (n - 1));
      var y = geom.top + geom.height - (geom.height * v) / geom.maxVal;
      return Math.round(x) + "," + Math.round(y);
    }).join(" ");
  }

  function finalSummary(rows) {
    var last = rows[rows.length - 1];
    return {
      allowable: last.cumulative_allowable, disallowed: last.cumulative_disallowed,
      remaining: last.remaining, projected: last.projected_total,
      variance: last.projected_variance, status: last.status, overdue: last.reports_overdue,
    };
  }

  var api = {
    parseRows: parseRows, parseTimelineCSV: parseTimelineCSV, formatMoney: formatMoney,
    statusClass: statusClass, buildSeries: buildSeries, pointsFor: pointsFor, finalSummary: finalSummary,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GrantTimeline = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
