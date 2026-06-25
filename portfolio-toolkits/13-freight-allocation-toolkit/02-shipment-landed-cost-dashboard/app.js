/*
 * DOM wiring for the Shipment Landed-Cost Dashboard.
 *
 * This file reads the chosen file with the FileReader API, hands the text to the
 * pure logic in dashboard_logic.js, and renders the result. It holds no business
 * rules. Nothing is sent anywhere; the file is read locally in the browser.
 */
(function () {
  "use strict";

  var logic = window.DashboardLogic;

  var fileInput = document.getElementById("csv-input");
  var loadButton = document.getElementById("load-button");
  var messageEl = document.getElementById("message");
  var summaryEl = document.getElementById("summary");
  var tableWrap = document.getElementById("table-wrap");
  var ledgerBody = document.getElementById("ledger-body");

  loadButton.addEventListener("click", handleLoad);
  fileInput.addEventListener("change", function () {
    // Loading the moment a file is picked keeps the flow simple, but the
    // button stays available for re-loading the same file.
    if (fileInput.files && fileInput.files.length > 0) {
      handleLoad();
    }
  });

  function handleLoad() {
    var file = fileInput.files && fileInput.files[0];
    if (!file) {
      showError(["Choose a CSV file first."]);
      return;
    }

    var reader = new FileReader();
    reader.onerror = function () {
      showError(["Could not read that file. Try choosing it again."]);
    };
    reader.onload = function () {
      render(String(reader.result), file.name);
    };
    reader.readAsText(file);
  }

  function render(text, fileName) {
    var parsed = logic.parseCsv(text);

    var missing = logic.missingColumns(parsed.header);
    if (missing.length > 0) {
      hideResults();
      showError([
        "This file is missing required column(s): " + missing.join(", ") + ".",
      ]);
      return;
    }

    if (parsed.records.length === 0) {
      hideResults();
      showError(["This file has a header but no data rows."]);
      return;
    }

    var built = logic.buildRows(parsed.records);

    if (built.errors.length > 0) {
      hideResults();
      showError(
        ["Found " + built.errors.length + " problem(s) in " + fileName + ":"],
        built.errors
      );
      return;
    }

    var totals = logic.summarize(built.rows);
    drawTable(built.rows);
    drawSummary(totals);
    showOk(
      "Loaded " +
        totals.lineCount +
        " line(s) from " +
        fileName +
        ". Total freight allocated " +
        logic.formatMoney(totals.totalFreightCents) +
        " ties to the carrier charge."
    );
  }

  function drawTable(rows) {
    ledgerBody.innerHTML = "";
    rows.forEach(function (row) {
      var tr = document.createElement("tr");
      tr.appendChild(cell(row.lineId));
      tr.appendChild(cell(row.description));
      tr.appendChild(cell(String(row.quantity), "num"));
      tr.appendChild(cell(logic.formatMoney(row.unitCostCents), "num"));
      tr.appendChild(cell(logic.formatMoney(row.allocatedFreightCents), "num"));
      tr.appendChild(cell(logic.formatMoney(row.landedUnitCostCents), "num"));
      ledgerBody.appendChild(tr);
    });
    tableWrap.hidden = false;
  }

  function cell(value, className) {
    var td = document.createElement("td");
    td.textContent = value;
    if (className) {
      td.className = className;
    }
    return td;
  }

  function drawSummary(totals) {
    document.getElementById("summary-lines").textContent = String(totals.lineCount);
    document.getElementById("summary-goods").textContent = logic.formatMoney(
      totals.totalGoodsCents
    );
    document.getElementById("summary-freight").textContent = logic.formatMoney(
      totals.totalFreightCents
    );
    document.getElementById("summary-landed").textContent = logic.formatMoney(
      totals.totalLandedCents
    );
    summaryEl.hidden = false;
  }

  function showError(lines, detailItems) {
    messageEl.className = "message error";
    messageEl.hidden = false;
    messageEl.innerHTML = "";
    lines.forEach(function (line) {
      var p = document.createElement("p");
      p.textContent = line;
      p.style.margin = "0";
      messageEl.appendChild(p);
    });
    if (detailItems && detailItems.length > 0) {
      var ul = document.createElement("ul");
      detailItems.forEach(function (item) {
        var li = document.createElement("li");
        li.textContent = item;
        ul.appendChild(li);
      });
      messageEl.appendChild(ul);
    }
  }

  function showOk(text) {
    messageEl.className = "message ok";
    messageEl.hidden = false;
    messageEl.textContent = text;
  }

  function hideResults() {
    summaryEl.hidden = true;
    tableWrap.hidden = true;
    ledgerBody.innerHTML = "";
  }
})();
