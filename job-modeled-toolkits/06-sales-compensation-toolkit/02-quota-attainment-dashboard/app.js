/*
 * app.js
 *
 * Thin DOM layer for the Quota Attainment Dashboard. It reads the chosen CSV
 * file with the FileReader API, hands the text to DashboardLogic, and renders
 * what comes back. No business rules live here; parsing, validation, banding,
 * and the summary are all in dashboard_logic.js.
 */
(function () {
  "use strict";

  var els = {
    csvFile: document.getElementById("csvFile"),
    fileName: document.getElementById("fileName"),
    error: document.getElementById("error"),
    errorText: document.getElementById("errorText"),
    summary: document.getElementById("summary"),
    statOver: document.getElementById("statOver"),
    statAt: document.getElementById("statAt"),
    statUnder: document.getElementById("statUnder"),
    statIssues: document.getElementById("statIssues"),
    summaryLine: document.getElementById("summaryLine"),
    tableCard: document.getElementById("tableCard"),
    resultRows: document.getElementById("resultRows"),
    issuesCard: document.getElementById("issuesCard"),
    issueRows: document.getElementById("issueRows")
  };

  var BAND_LABEL = { over: "Over quota", at: "At quota", under: "Under quota" };

  function hideAllOutput() {
    els.error.hidden = true;
    els.summary.hidden = true;
    els.tableCard.hidden = true;
    els.issuesCard.hidden = true;
  }

  function showError(message) {
    hideAllOutput();
    els.errorText.textContent = message;
    els.error.hidden = false;
  }

  function appendCell(tr, text, className) {
    var td = document.createElement("td");
    td.textContent = text;
    if (className) {
      td.className = className;
    }
    tr.appendChild(td);
  }

  function render(result) {
    hideAllOutput();

    // Summary
    els.statOver.textContent = result.summary.over;
    els.statAt.textContent = result.summary.at;
    els.statUnder.textContent = result.summary.under;
    els.statIssues.textContent = result.summary.issueCount;
    els.summaryLine.textContent =
      result.summary.validCount +
      " reps read. Team actual " +
      DashboardLogic.formatCents(result.summary.totalActualCents) +
      " against quota " +
      DashboardLogic.formatCents(result.summary.totalQuotaCents) +
      " (" +
      DashboardLogic.formatAttainment(result.summary.overallAttainment) +
      " overall).";
    els.summary.hidden = false;

    // Results table
    els.resultRows.innerHTML = "";
    result.reps.forEach(function (rep) {
      var tr = document.createElement("tr");
      tr.className = "band-" + rep.band;
      appendCell(tr, rep.repId);
      appendCell(tr, rep.repName);
      appendCell(tr, DashboardLogic.formatCents(rep.quotaCents), "amount");
      appendCell(tr, DashboardLogic.formatCents(rep.actualCents), "amount");
      appendCell(tr, DashboardLogic.formatAttainment(rep.attainment), "amount");

      var statusTd = document.createElement("td");
      var badge = document.createElement("span");
      badge.className = "badge badge-" + rep.band;
      badge.textContent = BAND_LABEL[rep.band];
      statusTd.appendChild(badge);
      tr.appendChild(statusTd);

      els.resultRows.appendChild(tr);
    });
    els.tableCard.hidden = result.reps.length === 0;

    // Issues
    els.issueRows.innerHTML = "";
    result.issues.forEach(function (issue) {
      var tr = document.createElement("tr");
      appendCell(tr, String(issue.lineNumber));
      appendCell(tr, issue.reason);
      els.issueRows.appendChild(tr);
    });
    els.issuesCard.hidden = result.issues.length === 0;
  }

  function handleFile(event) {
    var file = event.target.files && event.target.files[0];
    if (!file) {
      return;
    }
    els.fileName.textContent = file.name;
    var reader = new FileReader();
    reader.onload = function () {
      var result = DashboardLogic.analyze(String(reader.result));
      if (!result.ok) {
        showError(result.error);
        return;
      }
      render(result);
    };
    reader.onerror = function () {
      showError("The browser could not read that file.");
    };
    reader.readAsText(file);
    // Allow re-selecting the same file later.
    event.target.value = "";
  }

  els.csvFile.addEventListener("change", handleFile);
})();
