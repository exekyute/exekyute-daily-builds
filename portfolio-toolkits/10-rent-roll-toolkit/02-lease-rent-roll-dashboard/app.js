"use strict";

/*
 * Thin DOM wiring for the Lease and Rent Roll Dashboard.
 *
 * This file reads the chosen file with FileReader, calls the pure functions in
 * dashboard_logic.js, and puts the result on the page. It holds the last loaded
 * CSV text so changing the as-of date or the window re-renders without asking for
 * the file again. It does no money or date math of its own.
 */
(function () {
  var fileInput = document.getElementById("file");
  var asOfInput = document.getElementById("as-of");
  var windowInput = document.getElementById("window");

  var message = document.getElementById("message");
  var summary = document.getElementById("summary");
  var tablePanel = document.getElementById("table-panel");
  var rollBody = document.getElementById("roll-body");
  var issuesPanel = document.getElementById("issues-panel");
  var issuesList = document.getElementById("issues-list");

  var csvText = null;

  function showMessage(text, kind) {
    message.textContent = text;
    message.className = "message show " + kind;
  }

  function clearMessage() {
    message.textContent = "";
    message.className = "message";
  }

  function card(label, value, accent) {
    return (
      '<div class="card' +
      (accent ? " accent" : "") +
      '"><p class="card-label">' +
      label +
      '</p><p class="card-value">' +
      value +
      "</p></div>"
    );
  }

  function renderSummary(result) {
    var s = result.summary;
    var html = "";
    html += card("Units billed", String(s.count), false);
    html += card("Total billed", formatCents(s.totalBilledCents), false);
    html += card(
      "Expiring within " + s.windowDays + " days",
      String(s.flaggedCount),
      s.flaggedCount > 0
    );
    summary.innerHTML = html;
    summary.hidden = false;
  }

  function renderTable(units) {
    var html = "";
    for (var i = 0; i < units.length; i++) {
      var u = units[i];
      var badge = u.expiring ? ' <span class="badge">expiring</span>' : "";
      html +=
        "<tr" +
        (u.expiring ? ' class="expiring"' : "") +
        ">" +
        "<td>" +
        u.unit +
        "</td>" +
        "<td>" +
        u.tenant +
        "</td>" +
        '<td class="num">' +
        formatCents(u.monthlyCents) +
        "</td>" +
        '<td class="num">' +
        formatCents(u.proratedCents) +
        "</td>" +
        '<td class="num">' +
        formatCents(u.lateFeeCents) +
        "</td>" +
        '<td class="num">' +
        formatCents(u.amountDueCents) +
        "</td>" +
        "<td>" +
        u.leaseEnd +
        badge +
        "</td>" +
        '<td class="num">' +
        u.daysUntil +
        "</td>" +
        "</tr>";
    }
    rollBody.innerHTML = html;
    tablePanel.hidden = false;
  }

  function renderIssues(issues) {
    if (issues.length === 0) {
      issuesPanel.hidden = true;
      issuesList.innerHTML = "";
      return;
    }
    var html = "";
    for (var i = 0; i < issues.length; i++) {
      html += "<li>line " + issues[i].line + ": " + issues[i].reason + "</li>";
    }
    issuesList.innerHTML = html;
    issuesPanel.hidden = false;
  }

  function hideResults() {
    summary.hidden = true;
    tablePanel.hidden = true;
    issuesPanel.hidden = true;
  }

  function render() {
    if (csvText === null) {
      return;
    }
    var result = analyzeRentRoll(csvText, asOfInput.value, windowInput.value);
    if (!result.ok) {
      hideResults();
      showMessage(result.error, "error");
      return;
    }
    clearMessage();
    renderSummary(result);
    renderTable(result.units);
    renderIssues(result.issues);
    if (result.units.length === 0) {
      showMessage("No valid rows to show. See the skipped rows below.", "info");
    }
  }

  fileInput.addEventListener("change", function () {
    var file = fileInput.files[0];
    if (!file) {
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      csvText = reader.result;
      render();
    };
    reader.onerror = function () {
      showMessage("That file could not be read.", "error");
    };
    reader.readAsText(file);
  });

  asOfInput.addEventListener("change", render);
  windowInput.addEventListener("input", render);
})();
