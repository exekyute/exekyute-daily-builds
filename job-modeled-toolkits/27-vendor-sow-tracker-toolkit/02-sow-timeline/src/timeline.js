/* Timeline logic for the SOW earned-value view.
 *
 * Pure functions: parse the engine's timeline CSV, build the chart series, and
 * format values, with no DOM access. The chart wiring in chart.js calls these,
 * and the test harness in tests.js checks them. The figures match the Python
 * engine in 01 to the cent.
 *
 * Runs in the browser (attaches SowTimeline to the window) and under Node (it
 * exports the same object), so the tests run in either place.
 */
(function (global) {
  "use strict";

  var NUMERIC = ["cost_to_date", "earned_value", "percent_complete", "percent_spent",
    "cpi", "eac", "vac", "holdback_accrued", "holdback_released"];

  function parseTimelineCSV(text) {
    var lines = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n")
      .filter(function (l) { return l.trim() !== ""; });
    var headers = lines[0].split(",");
    return lines.slice(1).map(function (line) {
      var cells = line.split(",");
      var row = {};
      headers.forEach(function (h, i) {
        var key = h.trim();
        var value = (cells[i] || "").trim();
        row[key] = NUMERIC.indexOf(key) !== -1 ? Number(value) : (key === "week" ? Number(value) : value);
      });
      return row;
    });
  }

  function formatMoney(value) {
    return Number(value).toLocaleString("en-CA", { style: "currency", currency: "CAD" });
  }

  function formatPercent(ratio) {
    return (Number(ratio) * 100).toFixed(1) + "%";
  }

  function statusClass(status) {
    if (status === "Over budget") { return "over-budget"; }
    if (status === "At risk") { return "at-risk"; }
    return "on-track";
  }

  // Build the chart series. budget is the SOW total. maxVal drives the y scale,
  // taken from the highest cost or budget so both lines and the budget rule fit.
  function buildSeries(rows, budget) {
    var weeks = rows.map(function (r) { return r.week; });
    var cost = rows.map(function (r) { return r.cost_to_date; });
    var earned = rows.map(function (r) { return r.earned_value; });
    var maxVal = Math.max(budget, Math.max.apply(null, cost), Math.max.apply(null, earned));
    return { weeks: weeks, cost: cost, earned: earned, budget: budget, maxVal: maxVal };
  }

  // Map a series of values to SVG points across the plot area.
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
      eac: last.eac, vac: last.vac, holdbackReleased: last.holdback_released,
      status: last.status, percentComplete: last.percent_complete, percentSpent: last.percent_spent,
    };
  }

  var api = {
    parseTimelineCSV: parseTimelineCSV, formatMoney: formatMoney, formatPercent: formatPercent,
    statusClass: statusClass, buildSeries: buildSeries, pointsFor: pointsFor, finalSummary: finalSummary,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.SowTimeline = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
