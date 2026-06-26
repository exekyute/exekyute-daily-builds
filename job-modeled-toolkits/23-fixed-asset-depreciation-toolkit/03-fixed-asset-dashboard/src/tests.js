/*
 * Assertions for the dashboard's pure logic. Loaded by tests.html, which prints
 * PASS or FAIL on the page. No build step and no server: open tests.html in a
 * browser and read the result.
 */
(function () {
  "use strict";

  var FA = FixedAssets;
  var results = [];

  function check(name, condition) {
    results.push({ name: name, pass: !!condition });
  }

  function throws(fn) {
    try { fn(); return false; } catch (e) { return true; }
  }

  var classRows = FA.parseClassRows(SAMPLE_PER_CLASS_CSV);
  var byClass = {};
  classRows.forEach(function (r) { byClass[r.cca_class] = r; });

  check("dollarsToCents reads a plain amount", FA.dollarsToCents("12500.00") === 1250000);
  check("dollarsToCents reads a negative amount", FA.dollarsToCents("-6800.00") === -680000);

  check("class 8 CCA parses to 2500.00", byClass["8"].cca_cents === 250000);
  check("class 8 closing UCC parses to 12500.00", byClass["8"].closing_ucc_cents === 1250000);
  check("class 8 timing difference is -6800.00", byClass["8"].temporary_difference_cents === -680000);
  check("class 10 recapture is 3000.00", byClass["10"].recapture_cents === 300000);
  check("class 50 terminal loss is 900.00", byClass["50"].terminal_loss_cents === 90000);
  check("class 12 takes no CCA", byClass["12"].cca_cents === 0);

  check("pool identity holds for the half-year class", FA.poolIdentityHolds(byClass["8"]));
  check("pool identity holds for the recapture class", FA.poolIdentityHolds(byClass["10"]));
  check("pool identity holds for the terminal-loss class", FA.poolIdentityHolds(byClass["50"]));

  var summary = FA.summarize(classRows);
  check("total CCA across classes is 2500.00", summary.totals.cca === 250000);
  check("total recapture is 3000.00", summary.totals.recapture === 300000);
  check("total terminal loss is 900.00", summary.totals.terminalLoss === 90000);
  check("all pool identities hold on the sample", summary.allIdentitiesHold === true);
  check("bar scale covers the largest closing UCC", summary.maxBar >= 1250000);

  check("a missing column is rejected", throws(function () {
    FA.parseClassRows("cca_class,opening_ucc\n8,10000.00");
  }));
  check("a non-numeric amount is rejected", throws(function () {
    var bad = SAMPLE_PER_CLASS_CSV.replace("2500.00", "two thousand");
    FA.parseClassRows(bad);
  }));

  // Money formatting produces a Canadian dollar string.
  var formatted = FA.formatMoney(1250000);
  check("formatMoney shows a CAD amount", /12,500\.00/.test(formatted));

  document.addEventListener("DOMContentLoaded", function () {
    var passed = results.filter(function (r) { return r.pass; }).length;
    var summaryBox = document.getElementById("summary");
    var allPass = passed === results.length;
    summaryBox.textContent = passed + " of " + results.length + " checks passed";
    summaryBox.className = "summary " + (allPass ? "ok" : "fail");

    var list = document.getElementById("results");
    list.innerHTML = results.map(function (r) {
      return '<li class="' + (r.pass ? "pass" : "fail") + '">' +
        (r.pass ? "PASS" : "FAIL") + " - " + r.name + "</li>";
    }).join("");
  });
})();
