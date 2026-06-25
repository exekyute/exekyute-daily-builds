/*
 * Pure logic for the fixed-asset dashboard. No DOM access lives here, so the
 * test harness can load these functions and check the numbers directly. Money is
 * carried in integer cents and only formatted for display, so the figures match
 * the Python engine and the SQL rollforward to the cent.
 *
 * Everything attaches to a single global, FixedAssets, so the page works by
 * double-clicking index.html with no module loader and no server.
 */
var FixedAssets = (function () {
  "use strict";

  var CLASS_COLUMNS = [
    "cca_class", "opening_ucc", "additions", "disposals", "half_year_adjustment",
    "cca", "recapture", "terminal_loss", "closing_ucc", "net_book_value",
    "temporary_difference"
  ];

  var moneyFormat = new Intl.NumberFormat("en-CA", {
    style: "currency", currency: "CAD"
  });

  function splitLine(line) {
    var fields = [];
    var current = "";
    var inQuotes = false;
    for (var i = 0; i < line.length; i++) {
      var ch = line[i];
      if (ch === '"') {
        inQuotes = !inQuotes;
      } else if (ch === "," && !inQuotes) {
        fields.push(current);
        current = "";
      } else {
        current += ch;
      }
    }
    fields.push(current);
    return fields.map(function (f) { return f.trim(); });
  }

  // Parse a CSV string into an array of row objects keyed by the header.
  function parseCsv(text) {
    var lines = String(text).replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
    var header = null;
    var rows = [];
    for (var i = 0; i < lines.length; i++) {
      if (lines[i].trim() === "") continue;
      var fields = splitLine(lines[i]);
      if (header === null) { header = fields; continue; }
      var row = {};
      for (var c = 0; c < header.length; c++) {
        row[header[c]] = fields[c] === undefined ? "" : fields[c];
      }
      rows.push(row);
    }
    return { header: header || [], rows: rows };
  }

  // Convert a dollar string such as "12500.00" or "-6800.00" to integer cents.
  function dollarsToCents(text) {
    var s = String(text).trim();
    var value = Number(s);
    if (s === "" || !isFinite(value)) {
      throw new Error("expected a number but found '" + text + "'");
    }
    return Math.round(value * 100);
  }

  // Validate and parse the per-class CCA file into rows with cents fields.
  function parseClassRows(text) {
    var parsed = parseCsv(text);
    var missing = CLASS_COLUMNS.filter(function (col) {
      return parsed.header.indexOf(col) === -1;
    });
    if (missing.length > 0) {
      throw new Error("per-class file is missing column(s): " + missing.join(", "));
    }
    return parsed.rows.map(function (row) {
      var out = { cca_class: row.cca_class };
      CLASS_COLUMNS.slice(1).forEach(function (col) {
        try {
          out[col + "_cents"] = dollarsToCents(row[col]);
        } catch (err) {
          throw new Error("class " + row.cca_class + " " + col + ": " + err.message);
        }
      });
      return out;
    });
  }

  // The pool identity for one class: a class with recapture or a terminal loss
  // resets to zero, otherwise closing = opening + additions - disposals - CCA.
  function poolIdentityHolds(row) {
    if (row.recapture_cents > 0 || row.terminal_loss_cents > 0) {
      return row.closing_ucc_cents === 0;
    }
    var before = row.opening_ucc_cents + row.additions_cents - row.disposals_cents;
    return row.closing_ucc_cents === before - row.cca_cents;
  }

  // Totals and the per-chart scaling maxima used by the dashboard. Each chart
  // scales to its own largest value so the bars fill the width and stay
  // comparable within the chart, rather than being dwarfed by a figure from a
  // different chart.
  function summarize(classRows) {
    var totals = {
      opening: 0, additions: 0, disposals: 0, cca: 0,
      recapture: 0, terminalLoss: 0, closing: 0, netBookValue: 0
    };
    var maxCca = 1;
    var maxTiming = 1;
    classRows.forEach(function (row) {
      totals.opening += row.opening_ucc_cents;
      totals.additions += row.additions_cents;
      totals.disposals += row.disposals_cents;
      totals.cca += row.cca_cents;
      totals.recapture += row.recapture_cents;
      totals.terminalLoss += row.terminal_loss_cents;
      totals.closing += row.closing_ucc_cents;
      totals.netBookValue += row.net_book_value_cents;
      maxCca = Math.max(maxCca, row.cca_cents);
      maxTiming = Math.max(maxTiming, row.closing_ucc_cents, row.net_book_value_cents);
    });
    return {
      totals: totals,
      maxCca: maxCca,
      maxTiming: maxTiming,
      maxBar: Math.max(maxCca, maxTiming),
      classCount: classRows.length,
      allIdentitiesHold: classRows.every(poolIdentityHolds)
    };
  }

  function formatMoney(cents) {
    return moneyFormat.format(cents / 100);
  }

  return {
    parseCsv: parseCsv,
    dollarsToCents: dollarsToCents,
    parseClassRows: parseClassRows,
    poolIdentityHolds: poolIdentityHolds,
    summarize: summarize,
    formatMoney: formatMoney,
    CLASS_COLUMNS: CLASS_COLUMNS
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = FixedAssets;
}
