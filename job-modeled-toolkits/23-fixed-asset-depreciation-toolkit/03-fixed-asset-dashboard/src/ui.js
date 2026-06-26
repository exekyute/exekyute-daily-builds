/*
 * DOM wiring for the fixed-asset dashboard. This file reads the file input,
 * hands the text to the pure logic in dashboard.js, and paints the result. All
 * calculation lives in dashboard.js; this layer only moves values onto the page.
 * Files are read with the FileReader API and never leave the browser.
 */
(function () {
  "use strict";

  var FA = FixedAssets;
  var currentRows = null;

  function el(id) { return document.getElementById(id); }

  function setError(message) {
    var box = el("error");
    if (!message) {
      box.textContent = "";
      box.classList.remove("show");
      return;
    }
    box.textContent = message;
    box.classList.add("show");
  }

  function renderSummary(summary) {
    var cards = [
      ["Capital cost allowance", FA.formatMoney(summary.totals.cca)],
      ["Recapture", FA.formatMoney(summary.totals.recapture)],
      ["Terminal loss", FA.formatMoney(summary.totals.terminalLoss)],
      ["Closing UCC", FA.formatMoney(summary.totals.closing)]
    ];
    el("summary").innerHTML = cards.map(function (c) {
      return '<div class="card"><span class="card-label">' + c[0] +
        '</span><span class="card-value">' + c[1] + "</span></div>";
    }).join("");
  }

  function bar(valueCents, maxBar, kind) {
    var pct = maxBar > 0 ? (valueCents / maxBar) * 100 : 0;
    if (pct < 0) pct = 0;
    // A positive value always shows at least a thin sliver; a zero value shows
    // an empty track, so the chart never paints a bar where there is no amount.
    var fill = "";
    if (pct > 0) {
      var width = Math.max(pct, 1.5);
      fill = '<div class="bar-fill ' + kind + '" style="width:' + width + '%"></div>';
    }
    return '<div class="bar-track">' + fill + "</div>" +
      '<span class="bar-value">' + FA.formatMoney(valueCents) + "</span>";
  }

  function renderCcaChart(rows, summary) {
    el("cca-chart").innerHTML = rows.map(function (r) {
      return '<div class="chart-row"><span class="chart-key">Class ' + r.cca_class +
        "</span>" + bar(r.cca_cents, summary.maxCca, "accent") + "</div>";
    }).join("");
  }

  function renderTimingChart(rows, summary) {
    el("timing-chart").innerHTML = rows.map(function (r) {
      return '<div class="chart-row"><span class="chart-key">Class ' + r.cca_class +
        "</span>" +
        '<div class="bar-group">' +
        '<div class="bar-line"><span class="bar-tag">Book NBV</span>' +
        bar(r.net_book_value_cents, summary.maxTiming, "base") + "</div>" +
        '<div class="bar-line"><span class="bar-tag">Tax UCC</span>' +
        bar(r.closing_ucc_cents, summary.maxTiming, "accent") + "</div>" +
        "</div></div>";
    }).join("");
  }

  function flag(row) {
    if (row.recapture_cents > 0) return '<span class="flag recapture">recapture</span>';
    if (row.terminal_loss_cents > 0) return '<span class="flag terminal">terminal loss</span>';
    return "";
  }

  function renderTable(rows) {
    var head = ["Class", "Opening UCC", "Additions", "Disposals", "Half-year",
      "CCA", "Closing UCC", "Book NBV", "Timing diff", ""];
    var body = rows.map(function (r) {
      return "<tr>" +
        "<td>" + r.cca_class + "</td>" +
        "<td>" + FA.formatMoney(r.opening_ucc_cents) + "</td>" +
        "<td>" + FA.formatMoney(r.additions_cents) + "</td>" +
        "<td>" + FA.formatMoney(r.disposals_cents) + "</td>" +
        "<td>" + FA.formatMoney(r.half_year_adjustment_cents) + "</td>" +
        "<td>" + FA.formatMoney(r.cca_cents) + "</td>" +
        "<td>" + FA.formatMoney(r.closing_ucc_cents) + "</td>" +
        "<td>" + FA.formatMoney(r.net_book_value_cents) + "</td>" +
        "<td>" + FA.formatMoney(r.temporary_difference_cents) + "</td>" +
        "<td>" + flag(r) + "</td>" +
        "</tr>";
    }).join("");
    el("rollforward").innerHTML =
      "<thead><tr>" + head.map(function (h) { return "<th>" + h + "</th>"; }).join("") +
      "</tr></thead><tbody>" + body + "</tbody>";
  }

  function render(text) {
    var rows;
    try {
      rows = FA.parseClassRows(text);
    } catch (err) {
      setError("Could not read that file. " + err.message);
      return;
    }
    if (rows.length === 0) {
      setError("That file has no class rows.");
      return;
    }
    setError("");
    currentRows = rows;
    rows.sort(function (a, b) { return Number(a.cca_class) - Number(b.cca_class); });
    var summary = FA.summarize(rows);
    renderSummary(summary);
    renderCcaChart(rows, summary);
    renderTimingChart(rows, summary);
    renderTable(rows);

    var note = el("identity-note");
    if (summary.allIdentitiesHold) {
      note.textContent = "Pool identity holds for all " + summary.classCount + " classes.";
      note.className = "note ok";
    } else {
      note.textContent = "One or more classes do not satisfy the pool identity.";
      note.className = "note bad";
    }
  }

  function onFile(event) {
    var file = event.target.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function () { render(String(reader.result)); };
    reader.onerror = function () { setError("Could not open that file."); };
    reader.readAsText(file);
  }

  document.addEventListener("DOMContentLoaded", function () {
    el("file").addEventListener("change", onFile);
    el("load-sample").addEventListener("click", function () {
      render(SAMPLE_PER_CLASS_CSV);
    });
    render(SAMPLE_PER_CLASS_CSV);
  });
})();
