"use strict";

// Pure logic for the AI operations dashboard. No DOM access here. The UI layer in
// ui.js and the test harness in tests.js both call into this object. Money is handled
// in whole cents and formatted with Intl.NumberFormat, so amounts never show
// floating-point artifacts and the figures match the Python and SQL tools to the cent.

const Dashboard = (function () {
  const REQUIRED_TEAM_COLUMNS = [
    "team", "direct_cost", "allocated_shared", "loaded_cost",
    "monthly_budget", "forecast_loaded",
  ];
  const REQUIRED_SCORECARD_COLUMNS = [
    "rank", "model", "accuracy", "f1", "p95_latency_ms", "cost_per_correct", "score",
  ];
  const NEAR_LIMIT_PCT = 90;

  const moneyFormat = new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD",
  });

  // Split simple CSV text into a header list and an array of row objects. The data
  // files this dashboard reads have no quoted fields, so a plain split is enough.
  function parseCsv(text) {
    const lines = String(text).replace(/\r\n/g, "\n").trim().split("\n");
    if (lines.length < 2) {
      throw new Error("The file has no data rows.");
    }
    const headers = lines[0].split(",").map(function (h) { return h.trim(); });
    const rows = lines.slice(1).map(function (line) {
      const cells = line.split(",");
      const row = {};
      headers.forEach(function (header, i) {
        row[header] = (cells[i] === undefined ? "" : cells[i]).trim();
      });
      return row;
    });
    return { headers: headers, rows: rows };
  }

  function requireColumns(headers, required, label) {
    const missing = required.filter(function (col) {
      return headers.indexOf(col) === -1;
    });
    if (missing.length > 0) {
      throw new Error(label + " is missing column(s): " + missing.join(", "));
    }
  }

  // Turn a dollar string like "1143.60" into 114360 whole cents, rounding the third
  // decimal place half up. The compute tools write two-decimal money, so this is exact.
  function toCents(text) {
    const trimmed = String(text).trim();
    if (!/^-?\d+(\.\d+)?$/.test(trimmed)) {
      throw new Error("Expected a number, got " + JSON.stringify(text));
    }
    const negative = trimmed.charAt(0) === "-";
    const body = negative ? trimmed.slice(1) : trimmed;
    const parts = body.split(".");
    const whole = parts[0];
    const frac = (parts[1] || "") + "000";
    let cents = Number(whole) * 100 + Number(frac.slice(0, 2));
    if (Number(frac.charAt(2)) >= 5) {
      cents += 1;
    }
    return negative ? -cents : cents;
  }

  function formatMoney(cents) {
    return moneyFormat.format(cents / 100);
  }

  // Loaded cost as a percent of budget, rounded to one decimal place.
  function utilization(loadedCents, budgetCents) {
    if (budgetCents <= 0) {
      return 0;
    }
    return Math.round((loadedCents / budgetCents) * 1000) / 10;
  }

  // The same three-way label the cost engine applies, re-derived here so the
  // dashboard reaches its own verdict rather than trusting the input column.
  function deriveStatus(loadedCents, budgetCents) {
    if (loadedCents > budgetCents) {
      return "Over budget";
    }
    if (utilization(loadedCents, budgetCents) >= NEAR_LIMIT_PCT) {
      return "Near limit";
    }
    return "Within budget";
  }

  function summarizeTeams(text) {
    const parsed = parseCsv(text);
    requireColumns(parsed.headers, REQUIRED_TEAM_COLUMNS, "The team cost file");

    const teams = parsed.rows.map(function (row) {
      const loaded = toCents(row.loaded_cost);
      const budget = toCents(row.monthly_budget);
      const forecast = toCents(row.forecast_loaded);
      return {
        team: row.team,
        direct: toCents(row.direct_cost),
        shared: toCents(row.allocated_shared),
        loaded: loaded,
        budget: budget,
        remaining: budget - loaded,
        utilization: utilization(loaded, budget),
        status: deriveStatus(loaded, budget),
        forecast: forecast,
        forecastStatus: deriveStatus(forecast, budget),
      };
    });

    const totals = teams.reduce(function (acc, t) {
      acc.direct += t.direct;
      acc.shared += t.shared;
      acc.loaded += t.loaded;
      acc.budget += t.budget;
      acc.forecast += t.forecast;
      if (t.status === "Over budget") {
        acc.overCount += 1;
      }
      return acc;
    }, { direct: 0, shared: 0, loaded: 0, budget: 0, forecast: 0, overCount: 0 });

    teams.sort(function (a, b) { return b.loaded - a.loaded; });
    return { teams: teams, totals: totals };
  }

  function buildScorecard(text) {
    const parsed = parseCsv(text);
    requireColumns(parsed.headers, REQUIRED_SCORECARD_COLUMNS, "The scorecard file");

    const models = parsed.rows.map(function (row) {
      return {
        rank: Number(row.rank),
        model: row.model,
        accuracy: row.accuracy,
        f1: row.f1,
        p95: Number(row.p95_latency_ms),
        costPerCorrect: row.cost_per_correct,
        score: row.score,
      };
    });
    models.sort(function (a, b) { return a.rank - b.rank; });
    return { models: models, best: models.length > 0 ? models[0].model : null };
  }

  return {
    NEAR_LIMIT_PCT: NEAR_LIMIT_PCT,
    parseCsv: parseCsv,
    requireColumns: requireColumns,
    toCents: toCents,
    formatMoney: formatMoney,
    utilization: utilization,
    deriveStatus: deriveStatus,
    summarizeTeams: summarizeTeams,
    buildScorecard: buildScorecard,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = Dashboard;
}
