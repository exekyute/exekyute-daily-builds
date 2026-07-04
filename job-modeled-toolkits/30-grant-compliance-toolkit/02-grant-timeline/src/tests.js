/* Tests for the grant compliance view logic.
 *
 * Runs in the browser through tests.html and under Node with `node src/tests.js`.
 * The expected numbers match the Python engine in 01 to the cent.
 */
(function (global) {
  "use strict";

  var isNode = typeof module !== "undefined" && module.exports;
  var T = isNode ? require("./timeline.js") : global.GrantTimeline;
  var SAMPLE = isNode ? require("./sample-data.js") : global.GRANT_SAMPLE;

  function runTests() {
    var results = [];
    function check(name, got, want) {
      results.push({ name: name, ok: got === want, got: got, want: want });
    }

    var csv = "period,cumulative_allowable,cumulative_disallowed,burn_rate,remaining,projected_total,projected_variance,status,reports_overdue\n" +
      "4,100000.00,5000.00,25000.00,150000.00,300000.00,-50000.00,Over budget,1";
    var parsed = T.parseTimelineCSV(csv);
    check("parse row count", parsed.length, 1);
    check("parse projected", parsed[0].projected_total, 300000);
    check("parse status", parsed[0].status, "Over budget");

    check("format money", T.formatMoney(250000), "$250,000.00");
    check("format negative", T.formatMoney(-50000), "-$50,000.00");
    check("status over", T.statusClass("Over budget"), "over-budget");
    check("status on track", T.statusClass("On track"), "on-track");

    var rows = SAMPLE.timeline;
    var byPeriod = {};
    rows.forEach(function (r) { byPeriod[r.period] = r; });
    check("period 1 on track", byPeriod[1].status, "On track");
    check("period 1 allowable", byPeriod[1].cumulative_allowable, 16000);
    check("period 4 projected", byPeriod[4].projected_total, 300000);
    check("period 4 disallowed", byPeriod[4].cumulative_disallowed, 5000);

    var summary = T.finalSummary(rows);
    check("final allowable", T.formatMoney(summary.allowable), "$100,000.00");
    check("final remaining", T.formatMoney(summary.remaining), "$150,000.00");
    check("final projected", T.formatMoney(summary.projected), "$300,000.00");
    check("final variance", T.formatMoney(summary.variance), "-$50,000.00");
    check("final status", summary.status, "Over budget");
    check("final overdue", summary.overdue, 1);

    var series = T.buildSeries(rows, SAMPLE.awardTotal);
    check("series max value", series.maxVal, 304000);
    check("award total", SAMPLE.awardTotal, 250000);
    check("categories sum to award", SAMPLE.categories.reduce(function (a, c) { return a + c.budget; }, 0), 250000);

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
