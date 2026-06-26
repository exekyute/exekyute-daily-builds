/*
 * dashboard_logic.js
 *
 * Pure business logic for the Quota Attainment Dashboard. No DOM access and no
 * browser APIs, so every function here can be exercised directly from
 * tests.html. The page script (app.js) reads the chosen file with FileReader
 * and passes the text in here.
 *
 * Money is handled in integer cents. Attainment is the ratio of actual revenue
 * to quota, computed from those integer cents. A row is banded as under (below
 * 100%), at (exactly 100%), or over (above 100%). Bad rows are collected with a
 * line number and a reason rather than aborting the whole file, so one good row
 * is never lost to one bad neighbour.
 */
var DashboardLogic = (function () {
  "use strict";

  var REQUIRED_COLUMNS = ["rep_id", "rep_name", "quota", "actual_revenue"];

  var currencyFormatter = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD"
  });

  var percentFormatter = new Intl.NumberFormat("en-US", {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 1
  });

  // --- CSV parsing ----------------------------------------------------------

  // Split one CSV line into fields. Handles double-quoted fields and escaped
  // quotes ("") inside them, which is enough for names that contain a comma.
  function parseCsvLine(line) {
    var fields = [];
    var value = "";
    var inQuotes = false;
    var i;
    for (i = 0; i < line.length; i++) {
      var ch = line[i];
      if (inQuotes) {
        if (ch === '"') {
          if (line[i + 1] === '"') {
            value += '"';
            i++;
          } else {
            inQuotes = false;
          }
        } else {
          value += ch;
        }
      } else if (ch === '"') {
        inQuotes = true;
      } else if (ch === ",") {
        fields.push(value);
        value = "";
      } else {
        value += ch;
      }
    }
    fields.push(value);
    return fields.map(function (f) { return f.trim(); });
  }

  // Parse the whole file into a header and numbered data lines. Blank lines are
  // skipped. Line numbers are 1-based and count every physical line so they
  // match what the user sees in a spreadsheet or editor.
  function parseCsv(text) {
    var rawLines = String(text).replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
    var header = null;
    var dataLines = [];
    var i;
    for (i = 0; i < rawLines.length; i++) {
      var line = rawLines[i];
      if (line.trim() === "") {
        continue;
      }
      if (header === null) {
        header = parseCsvLine(line).map(function (h) { return h.toLowerCase(); });
      } else {
        dataLines.push({ fields: parseCsvLine(line), lineNumber: i + 1 });
      }
    }
    return { header: header, dataLines: dataLines };
  }

  // --- money parsing --------------------------------------------------------

  function parseMoneyToCents(value) {
    if (value === null || value === undefined) {
      return { ok: false, error: "is missing" };
    }
    var text = String(value).trim().replace(/[$,\s]/g, "");
    if (text === "") {
      return { ok: false, error: "is missing" };
    }
    if (!/^-?\d+(\.\d+)?$/.test(text)) {
      return { ok: false, error: "is not a number" };
    }
    var amount = Number(text);
    if (!isFinite(amount)) {
      return { ok: false, error: "is not a finite number" };
    }
    return { ok: true, cents: Math.round(amount * 100) };
  }

  // --- analysis -------------------------------------------------------------

  function bandFor(actualCents, quotaCents) {
    if (actualCents > quotaCents) {
      return "over";
    }
    if (actualCents < quotaCents) {
      return "under";
    }
    return "at";
  }

  // Validate and summarise a CSV of rep results. Returns either a structural
  // failure (no header, missing required column) or a full result with the
  // valid reps, the rejected rows, and a summary.
  function analyze(text) {
    var parsed = parseCsv(text);

    if (parsed.header === null) {
      return { ok: false, error: "The file is empty. It needs a header row and at least one rep." };
    }

    var missingColumns = REQUIRED_COLUMNS.filter(function (col) {
      return parsed.header.indexOf(col) === -1;
    });
    if (missingColumns.length > 0) {
      return {
        ok: false,
        error: "The file is missing required column(s): " + missingColumns.join(", ") + "."
      };
    }

    var idx = {};
    REQUIRED_COLUMNS.forEach(function (col) {
      idx[col] = parsed.header.indexOf(col);
    });

    var reps = [];
    var issues = [];
    var seenIds = {};

    parsed.dataLines.forEach(function (row) {
      var fields = row.fields;
      if (fields.length !== parsed.header.length) {
        issues.push({
          lineNumber: row.lineNumber,
          reason:
            "expected " + parsed.header.length + " fields, found " + fields.length,
          raw: fields.join(",")
        });
        return;
      }

      var reasons = [];
      var repId = fields[idx.rep_id];
      var repName = fields[idx.rep_name];

      if (repId === "") {
        reasons.push("rep_id is missing");
      } else if (Object.prototype.hasOwnProperty.call(seenIds, repId)) {
        reasons.push("duplicate rep_id '" + repId + "'");
      }
      if (repId !== "") {
        seenIds[repId] = true;
      }

      if (repName === "") {
        reasons.push("rep_name is missing");
      }

      var quota = parseMoneyToCents(fields[idx.quota]);
      if (!quota.ok) {
        reasons.push("quota " + quota.error);
      } else if (quota.cents <= 0) {
        reasons.push("quota must be greater than 0");
      }

      var actual = parseMoneyToCents(fields[idx.actual_revenue]);
      if (!actual.ok) {
        reasons.push("actual_revenue " + actual.error);
      } else if (actual.cents < 0) {
        reasons.push("actual_revenue cannot be negative");
      }

      if (reasons.length > 0) {
        issues.push({
          lineNumber: row.lineNumber,
          reason: reasons.join("; "),
          raw: fields.join(",")
        });
        return;
      }

      reps.push({
        repId: repId,
        repName: repName,
        quotaCents: quota.cents,
        actualCents: actual.cents,
        attainment: actual.cents / quota.cents,
        band: bandFor(actual.cents, quota.cents),
        lineNumber: row.lineNumber
      });
    });

    var summary = summarize(reps, issues);

    return {
      ok: true,
      reps: reps,
      issues: issues,
      summary: summary
    };
  }

  function summarize(reps, issues) {
    var under = 0;
    var at = 0;
    var over = 0;
    var totalQuota = 0;
    var totalActual = 0;

    reps.forEach(function (rep) {
      if (rep.band === "under") { under++; }
      else if (rep.band === "over") { over++; }
      else { at++; }
      totalQuota += rep.quotaCents;
      totalActual += rep.actualCents;
    });

    return {
      validCount: reps.length,
      issueCount: issues.length,
      under: under,
      at: at,
      over: over,
      totalQuotaCents: totalQuota,
      totalActualCents: totalActual,
      overallAttainment: totalQuota > 0 ? totalActual / totalQuota : null
    };
  }

  // --- formatting -----------------------------------------------------------

  function formatCents(cents) {
    return currencyFormatter.format(cents / 100);
  }

  function formatAttainment(ratio) {
    if (ratio === null || ratio === undefined) {
      return "n/a";
    }
    return percentFormatter.format(ratio);
  }

  return {
    REQUIRED_COLUMNS: REQUIRED_COLUMNS,
    parseCsvLine: parseCsvLine,
    parseCsv: parseCsv,
    parseMoneyToCents: parseMoneyToCents,
    bandFor: bandFor,
    analyze: analyze,
    formatCents: formatCents,
    formatAttainment: formatAttainment
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = DashboardLogic;
}
