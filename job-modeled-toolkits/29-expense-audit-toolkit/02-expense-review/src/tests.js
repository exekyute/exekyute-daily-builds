/* Tests for the expense review logic.
 *
 * Runs in the browser through tests.html and under Node with `node src/tests.js`.
 * The expected numbers match the Python auditor in 01 to the cent.
 */
(function (global) {
  "use strict";

  var isNode = typeof module !== "undefined" && module.exports;
  var A = isNode ? require("./audit.js") : global.ExpenseAudit;
  var SAMPLE = isNode ? require("./sample-data.js") : global.EXPENSE_SAMPLE;

  function validatedExpenses(policy) {
    return SAMPLE.expenses.map(function (raw) {
      var r = A.validateExpense(raw, policy);
      if (!r.ok) { throw new Error("sample row failed: " + r.error); }
      return r.value;
    });
  }

  function runTests() {
    var results = [];
    function check(name, got, want) {
      results.push({ name: name, ok: got === want, got: got, want: want });
    }

    var policy = A.buildPolicy(SAMPLE.policy);
    check("mileage 250km at 0.70", A.mileageAmountCents(250, policy.mileageRateCents), 17500);
    check("format money", A.formatMoney(17500), "$175.00");
    check("half-cent rounds up", A.toCents("0.005"), 1);

    var expenses = validatedExpenses(policy);
    var result = A.auditAll(expenses, policy);
    var byId = {};
    result.rows.forEach(function (r) { byId[r.expense_id] = r; });

    check("E-01 approved", byId["E-01"].status, "Approved");
    check("E-01 computed", byId["E-01"].computedCents, 17500);
    check("E-02 mileage mismatch", byId["E-02"].flags.join(","), "MILEAGE_MISMATCH");
    check("E-03 over cap", byId["E-03"].flags.join(","), "OVER_CAP");
    check("E-04 no receipt", byId["E-04"].flags.join(","), "NO_RECEIPT");
    check("E-05 approved", byId["E-05"].status, "Approved");
    check("E-06 duplicate", byId["E-06"].flags.indexOf("DUPLICATE") !== -1, true);
    check("E-07 duplicate", byId["E-07"].flags.indexOf("DUPLICATE") !== -1, true);

    var t = result.totals;
    check("total claimed", t.totalClaimed, 89000);
    check("flagged amount", t.flaggedAmount, 47500);
    check("approved amount", t.approvedAmount, 41500);
    check("approved count", t.approvedCount, 2);
    check("flagged count", t.flaggedCount, 5);
    check("over cap count", t.overCapCount, 1);
    check("no receipt count", t.noReceiptCount, 1);
    check("duplicate count", t.duplicateCount, 2);
    check("mileage mismatch count", t.mileageMismatchCount, 1);

    var bad = A.validateExpense({
      expense_id: "E-99", date: "2026-06-08", employee: "A. Singh",
      category: "Entertainment", amount: "120.00", km: "", receipt: "yes",
    }, policy);
    check("unknown category rejected", bad.ok, false);

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
