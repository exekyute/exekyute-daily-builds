"use strict";

// DOM wiring for the dashboard. This is the only layer that touches the page or reads
// files. All of the computation lives in dashboard.js. Files are read with the
// FileReader API and never sent anywhere, so everything stays on your machine.

(function () {
  const state = { team: null, scorecard: null };

  function el(id) { return document.getElementById(id); }

  function showError(message) {
    el("error").textContent = message;
  }

  function clearError() {
    el("error").textContent = "";
  }

  function statusClass(status) {
    if (status === "Over budget") { return "over"; }
    if (status === "Near limit") { return "near"; }
    return "within";
  }

  function renderSummary() {
    const box = el("summary");
    if (!state.team) {
      box.innerHTML = "";
      return;
    }
    const t = state.team.totals;
    const cards = [
      { label: "Loaded spend", value: Dashboard.formatMoney(t.loaded) },
      { label: "Total budget", value: Dashboard.formatMoney(t.budget) },
      { label: "Month-end forecast", value: Dashboard.formatMoney(t.forecast) },
      { label: "Teams over budget", value: String(t.overCount) },
    ];
    box.innerHTML = cards.map(function (c) {
      return '<div class="kpi"><span class="kpi-value">' + c.value +
        '</span><span class="kpi-label">' + c.label + "</span></div>";
    }).join("");
  }

  function renderTeams() {
    const panel = el("budget-panel");
    if (!state.team) {
      panel.innerHTML = "";
      return;
    }
    const teams = state.team.teams;
    const maxScale = teams.reduce(function (m, t) {
      return Math.max(m, t.loaded, t.budget);
    }, 1);

    const rows = teams.map(function (t) {
      const loadedPct = (t.loaded / maxScale) * 100;
      const budgetPct = (t.budget / maxScale) * 100;
      const cls = statusClass(t.status);
      return '' +
        '<div class="team-row">' +
          '<div class="team-head">' +
            '<span class="team-name">' + t.team + "</span>" +
            '<span class="badge ' + cls + '">' + t.status + "</span>" +
          "</div>" +
          '<div class="bar-track">' +
            '<div class="bar-budget" style="width:' + budgetPct.toFixed(2) + '%"></div>' +
            '<div class="bar-loaded ' + cls + '" style="width:' + loadedPct.toFixed(2) + '%"></div>' +
          "</div>" +
          '<div class="team-figures">' +
            "<span>" + Dashboard.formatMoney(t.loaded) + " of " +
              Dashboard.formatMoney(t.budget) + "</span>" +
            "<span>" + t.utilization.toFixed(1) + "% used</span>" +
            "<span>forecast " + Dashboard.formatMoney(t.forecast) + "</span>" +
          "</div>" +
        "</div>";
    }).join("");
    panel.innerHTML = rows;
  }

  function renderScorecard() {
    const wrap = el("scorecard-panel");
    if (!state.scorecard) {
      wrap.innerHTML = "";
      return;
    }
    const head =
      "<thead><tr>" +
        "<th>Rank</th><th>Model</th><th>Accuracy</th><th>F1</th>" +
        "<th>p95 latency</th><th>Cost / correct</th><th>Score</th>" +
      "</tr></thead>";
    const body = state.scorecard.models.map(function (m) {
      const best = m.rank === 1 ? " best" : "";
      return '<tr class="score-row' + best + '">' +
        "<td>" + m.rank + "</td>" +
        "<td>" + m.model + "</td>" +
        "<td>" + m.accuracy + "</td>" +
        "<td>" + m.f1 + "</td>" +
        "<td>" + m.p95 + " ms</td>" +
        "<td>$" + m.costPerCorrect + "</td>" +
        '<td class="score-cell">' + m.score + "</td>" +
      "</tr>";
    }).join("");
    wrap.innerHTML = "<table class=\"table\">" + head + "<tbody>" + body + "</tbody></table>";
  }

  function renderAll() {
    renderSummary();
    renderTeams();
    renderScorecard();
  }

  function loadTeamText(text) {
    try {
      state.team = Dashboard.summarizeTeams(text);
      clearError();
      renderAll();
    } catch (err) {
      showError(err.message);
    }
  }

  function loadScorecardText(text) {
    try {
      state.scorecard = Dashboard.buildScorecard(text);
      clearError();
      renderAll();
    } catch (err) {
      showError(err.message);
    }
  }

  function readFile(input, handler) {
    const file = input.files && input.files[0];
    if (!file) { return; }
    const reader = new FileReader();
    reader.onload = function () { handler(String(reader.result)); };
    reader.onerror = function () { showError("Could not read that file."); };
    reader.readAsText(file);
  }

  document.addEventListener("DOMContentLoaded", function () {
    el("team-file").addEventListener("change", function () {
      readFile(this, loadTeamText);
    });
    el("scorecard-file").addEventListener("change", function () {
      readFile(this, loadScorecardText);
    });
    el("load-sample").addEventListener("click", function () {
      loadTeamText(Dashboard.SAMPLE_TEAM);
      loadScorecardText(Dashboard.SAMPLE_SCORECARD);
    });

    // Show the sample view on first open so the page is populated without a click.
    // Loading your own files replaces it.
    loadTeamText(Dashboard.SAMPLE_TEAM);
    loadScorecardText(Dashboard.SAMPLE_SCORECARD);
  });
})();
