"use strict";

// Test harness for the dashboard logic. Imports dashboard.js and the sample data,
// runs assertions against the pure functions, and prints PASS or FAIL on the page.
// Open tests.html to run it. No build step, no framework.

(function () {
  const results = [];

  function check(name, condition) {
    results.push({ name: name, pass: !!condition });
  }

  function throws(name, fn) {
    let threw = false;
    try { fn(); } catch (e) { threw = true; }
    results.push({ name: name, pass: threw });
  }

  // toCents rounds dollar strings to whole cents.
  check("toCents whole dollars", Dashboard.toCents("1143.60") === 114360);
  check("toCents half cent up", Dashboard.toCents("10.135") === 1014);
  check("toCents negative", Dashboard.toCents("-143.60") === -14360);
  check("toCents two-place exact", Dashboard.toCents("66.19") === 6619);

  // utilization and status mirror the cost engine.
  check("utilization rounds to one place", Dashboard.utilization(114360, 100000) === 114.4);
  check("status over budget", Dashboard.deriveStatus(114360, 100000) === "Over budget");
  check("status near limit", Dashboard.deriveStatus(13785, 15000) === "Near limit");
  check("status within budget", Dashboard.deriveStatus(7302, 20000) === "Within budget");

  // summarizeTeams over the sample data.
  const team = Dashboard.summarizeTeams(Dashboard.SAMPLE_TEAM);
  const byTeam = {};
  team.teams.forEach(function (t) { byTeam[t.team] = t; });

  check("four teams", team.teams.length === 4);
  check("teams sorted by loaded cost", team.teams[0].team === "Engineering");
  check("Engineering loaded cents", byTeam.Engineering.loaded === 114360);
  check("Engineering flagged over", byTeam.Engineering.status === "Over budget");
  check("Sales flagged near", byTeam.Sales.status === "Near limit");
  check("Support within budget", byTeam.Support.status === "Within budget");
  check("Sales forecast crosses budget", byTeam.Sales.forecastStatus === "Over budget");
  check("loaded total cents", team.totals.loaded === 161585);
  check("budget total cents", team.totals.budget === 175000);
  check("one team over budget", team.totals.overCount === 1);
  check("loaded total formats", Dashboard.formatMoney(team.totals.loaded) === "$1,615.85");

  // buildScorecard over the sample data.
  const card = Dashboard.buildScorecard(Dashboard.SAMPLE_SCORECARD);
  check("three models", card.models.length === 3);
  check("ranked best first", card.models[0].model === "frontier-mini");
  check("best model reported", card.best === "frontier-mini");
  check("top score", card.models[0].score === "80.00");
  check("frontier-large p95", card.models[2].p95 === 2000);

  // Validation rejects a file missing a required column.
  throws("team file missing column rejected", function () {
    Dashboard.summarizeTeams("team,loaded_cost\nSales,100.00");
  });
  throws("scorecard missing column rejected", function () {
    Dashboard.buildScorecard("rank,model\n1,frontier-mini");
  });
  throws("non-number money rejected", function () {
    Dashboard.toCents("n/a");
  });

  // Render to the page.
  const passed = results.filter(function (r) { return r.pass; }).length;
  const total = results.length;
  const summary = document.getElementById("summary");
  summary.textContent = passed + " of " + total + " passed";
  summary.className = "summary " + (passed === total ? "ok" : "fail");

  const list = document.getElementById("results");
  list.innerHTML = results.map(function (r) {
    return '<li class="' + (r.pass ? "pass" : "fail") + '">' +
      (r.pass ? "PASS" : "FAIL") + " - " + r.name + "</li>";
  }).join("");
})();
