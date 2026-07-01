/* Tests for the SOW timeline view logic.
 *
 * Runs in the browser through tests.html and under Node with `node src/tests.js`.
 * The expected numbers match the Python engine in 01 to the cent.
 */
(function (global) {
  "use strict";

  var isNode = typeof module !== "undefined" && module.exports;
  var T = isNode ? require("./timeline.js") : global.SowTimeline;
  var SAMPLE = isNode ? require("./sample-data.js") : global.SOW_SAMPLE;

  function runTests() {
    var results = [];
    function check(name, got, want) {
      results.push({ name: name, ok: got === want, got: got, want: want });
    }

    var csv = "week,cost_to_date,earned_value,percent_complete,percent_spent,cpi,eac,vac,holdback_accrued,holdback_released,status\n" +
      "1,21000.00,20000.00,0.2500,0.2625,0.9524,84000.00,-4000.00,2000.00,0.00,At risk";
    var parsed = T.parseTimelineCSV(csv);
    check("parse row count", parsed.length, 1);
    check("parse numeric eac", parsed[0].eac, 84000);
    check("parse status string", parsed[0].status, "At risk");

    check("format money", T.formatMoney(85000), "$85,000.00");
    check("format negative money", T.formatMoney(-5000), "-$5,000.00");
    check("format percent", T.formatPercent(0.25), "25.0%");
    check("status class over", T.statusClass("Over budget"), "over-budget");
    check("status class at risk", T.statusClass("At risk"), "at-risk");
    check("status class on track", T.statusClass("On track"), "on-track");

    var rows = SAMPLE.timeline;
    var byWeek = {};
    rows.forEach(function (r) { byWeek[r.week] = r; });

    check("week 3 cost", byWeek[3].cost_to_date, 52000);
    check("week 3 earned", byWeek[3].earned_value, 50000);
    check("week 3 eac", byWeek[3].eac, 83200);

    var summary = T.finalSummary(rows);
    check("final eac", T.formatMoney(summary.eac), "$85,000.00");
    check("final vac", T.formatMoney(summary.vac), "-$5,000.00");
    check("final holdback released", T.formatMoney(summary.holdbackReleased), "$8,000.00");
    check("final status", summary.status, "Over budget");
    check("final percent complete", summary.percentComplete, 1);

    var series = T.buildSeries(rows, SAMPLE.totalBudget);
    check("series max value", series.maxVal, 85000);
    check("series weeks", series.weeks.length, 5);

    var passed = results.filter(function (r) { return r.ok; }).length;
    return { passed: passed, failed: results.length - passed, results: results };
  }

  if (isNode) {
    var r = runTests();
    r.results.forEach(function (c) {
      if (!c.ok) { console.log("FAIL " + c.name + ": got " + c.got + ", want " + c.want); }
    });
    console.log((r.failed ? "FAIL" : "PASS") + ": " + r.passed + " of " + (r.passed + r.failed) + " checks");
    process.exitCode = r.failed ? 1 : 0;
  } else {
    global.runTests = runTests;
  }
})(typeof window !== "undefined" ? window : globalThis);
