/*
 * Test harness for the dashboard logic. Imported by tests.html with plain script
 * tags, so it runs by double-clicking the page. It checks the pure functions in
 * dashboard.js against the bundled sample data and prints PASS or FAIL on the
 * page, mirroring the figures the Python and SQL tools produce.
 */
(function () {
  "use strict";

  var D = Dashboard;
  var results = [];

  function check(name, actual, expected) {
    var pass = actual === expected;
    results.push({ name: name, pass: pass, actual: actual, expected: expected });
  }

  var perpetual = D.parseCsv(SAMPLE_DATA.perpetual);
  var batches = D.parseCsv(SAMPLE_DATA.batches);
  var margins = D.parseCsv(SAMPLE_DATA.margins);
  var excise = D.parseCsv(SAMPLE_DATA.excise);
  var physical = D.parseCsv(SAMPLE_DATA.physical);

  // Parsing
  check("perpetual parses 11 rows", perpetual.length, 11);
  check("margins parse 6 rows", margins.length, 6);

  // Money parsing in cents
  check("toCents handles two decimals", D.toCents("1234.56"), 123456);
  check("toCents handles a negative value", D.toCents("-8.00"), -800);

  // Valuation totals (match the perpetual valuation tool and the SQL close)
  check("total inventory value", D.totalInventory(perpetual), 1724079);
  var cats = D.valuationByCategory(perpetual);
  var byCat = {};
  cats.forEach(function (c) { byCat[c.category] = c.valueCents; });
  check("raw material value", byCat.raw_material, 816777);
  check("packaging value", byCat.packaging_material, 799718);
  check("finished goods value", byCat.finished_goods, 107584);

  // Batch waterfall (matches the batch tool total)
  var w = D.batchWaterfall(batches);
  check("batch waterfall total", w.totalCents, 635599);
  check("waterfall steps sum to total",
    w.steps.reduce(function (s, x) { return s + x.valueCents; }, 0), 635599);

  // Excise (matches the excise duty engine and the SQL close)
  var ex = D.exciseByClass(excise);
  check("excise duty total", ex.reduce(function (s, r) { return s + r.dutyCents; }, 0), 14917);

  // Margin ranking
  var ranked = D.skuMarginRanking(margins);
  check("top margin is the radler can", ranked[0].fg_sku, "FG-RADLER-CAN");
  check("top margin value", ranked[0].marginCents, 859041);

  // Reconciliation and exceptions (matches the SQL close)
  var reconciled = D.reconcile(perpetual, physical);
  var hops = reconciled.filter(function (r) { return r.sku === "RM-HOPS"; })[0];
  check("hops value variance in cents", hops.valueVarCents, -15744);
  check("hops over tolerance", hops.status, "over tolerance");
  check("exception count", D.exceptions(reconciled).length, 2);

  // Render
  var passed = results.filter(function (r) { return r.pass; }).length;
  var total = results.length;
  var root = document.getElementById("results");
  var summary = document.getElementById("summary");
  summary.textContent = passed + " / " + total + " checks passed";
  summary.className = passed === total ? "summary ok" : "summary fail";

  var html = "";
  results.forEach(function (r) {
    html +=
      '<li class="' + (r.pass ? "pass" : "fail") + '">' +
      (r.pass ? "PASS" : "FAIL") + " : " + r.name +
      (r.pass ? "" : " (got " + r.actual + ", expected " + r.expected + ")") +
      "</li>";
  });
  root.innerHTML = html;
})();
