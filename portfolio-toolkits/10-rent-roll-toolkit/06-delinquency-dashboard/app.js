"use strict";

/*
 * Thin DOM wiring for the Delinquency Dashboard.
 *
 * This file reads the chosen file with FileReader, calls the pure functions in
 * delinquency_logic.js, and renders the result. It does no money or date math of
 * its own.
 */
(function () {
  var fileInput = document.getElementById("file");
  var message = document.getElementById("message");
  var summary = document.getElementById("summary");
  var bucketsPanel = document.getElementById("buckets-panel");
  var bucketsBody = document.getElementById("buckets-body");
  var tablePanel = document.getElementById("table-panel");
  var chargesBody = document.getElementById("charges-body");
  var issuesPanel = document.getElementById("issues-panel");
  var issuesList = document.getElementById("issues-list");

  function showMessage(text, kind) {
    message.textContent = text;
    message.className = "message show " + kind;
  }

  function clearMessage() {
    message.textContent = "";
    message.className = "message";
  }

  function sevClass(bucket) {
    return "sev-" + bucketRank(bucket);
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

  function renderSummary(s) {
    var html = "";
    html += card("Delinquent charges", String(s.count), false);
    html += card("Open balance", formatCents(s.totalBalanceCents), false);
    html += card("Late fees", formatCents(s.totalLateFeeCents), false);
    html += card("Total owed", formatCents(s.totalOwedCents), s.totalOwedCents > 0);
    summary.innerHTML = html;
    summary.hidden = false;
  }

  function renderBuckets(s) {
    var html = "";
    for (var i = 0; i < BUCKET_ORDER.length; i++) {
      var name = BUCKET_ORDER[i];
      var b = s.buckets[name];
      html +=
        '<tr class="' + sevClass(name) + '">' +
        "<td>" + name + "</td>" +
        '<td class="num">' + b.count + "</td>" +
        '<td class="num">' + formatCents(b.balanceCents) + "</td>" +
        '<td class="num">' + formatCents(b.lateFeeCents) + "</td>" +
        '<td class="num">' + formatCents(b.owedCents) + "</td>" +
        "</tr>";
    }
    bucketsBody.innerHTML = html;
    bucketsPanel.hidden = false;
  }

  function renderCharges(rows) {
    var sorted = sortWorstFirst(rows);
    var html = "";
    for (var i = 0; i < sorted.length; i++) {
      var r = sorted[i];
      html +=
        '<tr class="' + sevClass(r.bucket) + '">' +
        "<td>" + r.unit + "</td>" +
        "<td>" + r.tenant + "</td>" +
        "<td>" + r.chargeType + "</td>" +
        "<td>" + r.dueDate + "</td>" +
        '<td class="num">' + formatCents(r.balanceCents) + "</td>" +
        '<td class="num">' + r.daysOverdue + "</td>" +
        '<td><span class="badge ' + sevClass(r.bucket) + '">' + r.bucket + "</span></td>" +
        '<td class="num">' + formatCents(r.lateFeeCents) + "</td>" +
        '<td class="num">' + formatCents(r.owedCents) + "</td>" +
        "</tr>";
    }
    chargesBody.innerHTML = html;
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
    bucketsPanel.hidden = true;
    tablePanel.hidden = true;
    issuesPanel.hidden = true;
  }

  function loadText(text) {
    var result = analyzeAging(text);
    if (!result.ok) {
      hideResults();
      showMessage(result.error, "error");
      return;
    }
    clearMessage();
    renderSummary(result.summary);
    renderBuckets(result.summary);
    renderCharges(result.rows);
    renderIssues(result.issues);
    if (result.rows.length === 0) {
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
})();
