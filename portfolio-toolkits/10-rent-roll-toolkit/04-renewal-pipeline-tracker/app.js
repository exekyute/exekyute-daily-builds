"use strict";

/*
 * Thin DOM wiring for the Renewal Pipeline Tracker.
 *
 * This file reads the chosen file with FileReader, calls the pure functions in
 * tracker_logic.js, and renders the result. It remembers the last parsed rows and
 * the current sort so clicking a column heading re-sorts without re-reading the
 * file. It does no money or date math of its own.
 */
(function () {
  var fileInput = document.getElementById("file");
  var message = document.getElementById("message");
  var summary = document.getElementById("summary");
  var tablePanel = document.getElementById("table-panel");
  var pipelineBody = document.getElementById("pipeline-body");
  var issuesPanel = document.getElementById("issues-panel");
  var issuesList = document.getElementById("issues-list");
  var headings = document.querySelectorAll("th.sortable");

  var currentRows = null;
  var sortKey = "default";
  var sortDirection = "asc";

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
    var c = result.summary.counts;
    var html = "";
    html += card("Leases", String(result.summary.count), false);
    html += card("Due now", String(c.due_now), c.due_now > 0);
    html += card("Upcoming", String(c.upcoming), false);
    html += card("Expired", String(c.expired), false);
    summary.innerHTML = html;
    summary.hidden = false;
  }

  function statusBadge(status) {
    var label = status === "due_now" ? "due now" : status;
    return '<span class="badge status-' + status + '">' + label + "</span>";
  }

  function renderTable(rows) {
    var sorted = sortRows(rows, sortKey, sortDirection);
    var html = "";
    for (var i = 0; i < sorted.length; i++) {
      var r = sorted[i];
      var flag =
        r.status === "due_now"
          ? ' <span class="notice-flag">send notice</span>'
          : "";
      html +=
        '<tr class="row-' + r.status + '">' +
        "<td>" + r.unit + "</td>" +
        "<td>" + r.tenant + "</td>" +
        '<td class="num">' + formatCents(r.currentCents) + "</td>" +
        '<td class="num">' + formatCents(r.escalatedCents) + "</td>" +
        "<td>" + r.leaseEnd + "</td>" +
        "<td>" + r.renewalStart + " to " + r.renewalEnd + "</td>" +
        "<td>" + r.noticeDue + "</td>" +
        '<td class="num">' + r.daysToNotice + flag + "</td>" +
        "<td>" + statusBadge(r.status) + "</td>" +
        "</tr>";
    }
    pipelineBody.innerHTML = html;
    tablePanel.hidden = false;
    updateHeadingArrows();
  }

  function updateHeadingArrows() {
    for (var i = 0; i < headings.length; i++) {
      var th = headings[i];
      var existing = th.querySelector(".arrow");
      if (existing) {
        existing.remove();
      }
      if (th.getAttribute("data-key") === sortKey) {
        var arrow = document.createElement("span");
        arrow.className = "arrow";
        arrow.textContent = sortDirection === "asc" ? "▲" : "▼";
        th.appendChild(arrow);
      }
    }
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
    if (currentRows === null) {
      return;
    }
    renderTable(currentRows);
  }

  function loadText(text) {
    var result = analyzeRenewals(text);
    if (!result.ok) {
      currentRows = null;
      hideResults();
      showMessage(result.error, "error");
      return;
    }
    clearMessage();
    currentRows = result.rows;
    sortKey = "default";
    sortDirection = "asc";
    renderSummary(result);
    renderTable(currentRows);
    renderIssues(result.issues);
    if (currentRows.length === 0) {
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
      loadText(reader.result);
    };
    reader.onerror = function () {
      showMessage("That file could not be read.", "error");
    };
    reader.readAsText(file);
  });

  for (var i = 0; i < headings.length; i++) {
    headings[i].addEventListener("click", function () {
      var key = this.getAttribute("data-key");
      if (sortKey === key) {
        sortDirection = sortDirection === "asc" ? "desc" : "asc";
      } else {
        sortKey = key;
        sortDirection = "asc";
      }
      render();
    });
  }
})();
