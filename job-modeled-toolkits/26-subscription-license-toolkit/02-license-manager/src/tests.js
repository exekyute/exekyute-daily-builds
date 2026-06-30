/* Tests for the license manager logic.
 *
 * Runs in the browser through tests.html, which prints PASS or FAIL on the page,
 * and under Node with `node src/tests.js`. The expected numbers match the Python
 * ledger in 01 to the cent, which is the proof the two tools agree.
 */
(function (global) {
  "use strict";

  var isNode = typeof module !== "undefined" && module.exports;
  var Logic = isNode ? require("./subscriptions.js") : global.SubLogic;
  var SAMPLE = isNode ? require("./sample-data.js") : global.SAMPLE_SUBSCRIPTIONS;
  var AS_OF = "2026-06-30";

  function validatedSample() {
    return SAMPLE.map(function (raw) {
      var result = Logic.validateSub(raw);
      if (!result.ok) { throw new Error("sample row failed validation: " + result.error); }
      return result.value;
    });
  }

  function runTests() {
    var results = [];
    function check(name, got, want) {
      results.push({ name: name, ok: got === want, got: got, want: want });
    }

    check("per-seat monthly cost", Logic.monthlyCostCents("per_seat", 1200, 50), 60000);
    check("flat monthly cost ignores seats", Logic.monthlyCostCents("flat", 30000, 10), 30000);
    check("monthly waste on 12 unused seats", Logic.monthlyWasteCents("per_seat", 1200, 50, 38), 14400);
    check("flat plan has no waste", Logic.monthlyWasteCents("flat", 30000, 10, 4), 0);
    check("utilization 38 of 50", Logic.utilization("per_seat", 50, 38), 0.76);
    check("half-cent rounds up", Logic.toCents("10.005"), 1001);
    check("days to renewal", Logic.daysToRenewal(AS_OF, "2026-07-20"), 20);
    check("renewal status due soon", Logic.renewalStatus(5), "Due soon");
    check("renewal status expired", Logic.renewalStatus(-3), "Expired");
    check("action auto-renew and underused", Logic.action("per_seat", 20, true, 0.45), "Auto-renews soon, underused");

    var summary = Logic.summarize(validatedSample(), AS_OF);
    var byId = {};
    summary.rows.forEach(function (r) { byId[r.sub_id] = r; });

    check("S-01 monthly cost", byId["S-01"].monthlyCents, 60000);
    check("S-01 annual waste", byId["S-01"].annualWasteCents, 172800);
    check("S-01 action", byId["S-01"].action, "OK");
    check("S-02 action", byId["S-02"].action, "Auto-renews soon, underused");
    check("S-05 status expired", byId["S-05"].renewalStatus, "Expired");
    check("S-03 flat utilization is null", byId["S-03"].utilization, null);

    check("portfolio monthly cost", summary.totals.monthlyCents, 367500);
    check("portfolio annual cost", summary.totals.annualCents, 4410000);
    check("portfolio monthly waste", summary.totals.monthlyWasteCents, 98400);
    check("portfolio annual waste", summary.totals.annualWasteCents, 1180800);
    check("due soon count", summary.totals.dueSoonCount, 2);
    check("expired count", summary.totals.expiredCount, 1);
    check("underused count", summary.totals.underusedCount, 2);

    var bad = Logic.validateSub({
      sub_id: "S-99", vendor: "Glitch Co", plan: "Bad", plan_type: "per_seat",
      monthly_unit_cost: "10", seats_owned: "5", seats_used: "9",
      renewal_date: "2026-08-01", auto_renew: "yes",
    });
    check("invalid row rejected", bad.ok, false);

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
