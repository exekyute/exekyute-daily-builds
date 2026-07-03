/* Page wiring for the expense review queue.
 *
 * Holds the expenses, runs the audit, shows each line with its flags, and lets a
 * reviewer approve or reject the flagged ones with a reason. Decisions and the
 * expense list are kept in localStorage so the review survives a refresh. All of
 * the audit logic lives in audit.js; this file only moves values to and from the page.
 */
(function () {
  "use strict";

  var A = window.ExpenseAudit;
  var STORAGE_KEY = "expense-review-state-v1";

  var state = { expenses: [], decisions: {}, filter: "all" };
  var policy = null;

  function load() {
    policy = A.buildPolicy(window.EXPENSE_SAMPLE.policy);
    var stored = null;
    try { stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY)); } catch (e) { stored = null; }
    if (stored && Array.isArray(stored.expenses) && stored.expenses.length) {
      state.expenses = stored.expenses;
      state.decisions = stored.decisions || {};
    } else {
      state.expenses = window.EXPENSE_SAMPLE.expenses.map(clone);
      state.decisions = {};
    }
  }

  function clone(obj) { return JSON.parse(JSON.stringify(obj)); }
  function persist() {
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (e) { /* off */ }
  }

  function audited() {
    var valid = [];
    state.expenses.forEach(function (raw) {
      var r = A.validateExpense(raw, policy);
      if (r.ok) { valid.push(r.value); }
    });
    return A.auditAll(valid, policy);
  }

  function decisionFor(row) {
    var d = state.decisions[row.expense_id];
    if (d && d.decision) { return d.decision; }
    return row.flags.length ? "pending" : "approved";
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) { Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]); }); }
    (children || []).forEach(function (c) {
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function renderTable() {
    var result = audited();
    var tbody = document.getElementById("rows");
    tbody.innerHTML = "";
    result.rows.forEach(function (row) {
      var decision = decisionFor(row);
      var tr = el("tr", { "data-id": row.expense_id, "class": "decision-" + decision + (row.flags.length ? " flagged" : " clean") });

      tr.appendChild(el("td", null, [row.expense_id]));
      tr.appendChild(el("td", null, [row.date]));
      tr.appendChild(el("td", null, [row.employee]));
      tr.appendChild(el("td", null, [row.category]));
      tr.appendChild(el("td", { "class": "num" }, [A.formatMoney(row.amountCents)]));

      var flagsCell = el("td");
      if (row.flags.length) {
        row.flags.forEach(function (f) { flagsCell.appendChild(el("span", { "class": "pill flag" }, [f.replace(/_/g, " ").toLowerCase()])); });
      } else {
        flagsCell.appendChild(el("span", { "class": "pill ok" }, ["clean"]));
      }
      tr.appendChild(flagsCell);

      var decisionCell = el("td", { "class": "decision-cell" });
      if (row.flags.length) {
        var approve = el("button", { "class": "chip approve" }, ["Approve"]);
        var reject = el("button", { "class": "chip reject" }, ["Reject"]);
        approve.addEventListener("click", function () { setDecision(row.expense_id, "approved"); });
        reject.addEventListener("click", function () { setDecision(row.expense_id, "rejected"); });
        var reason = el("input", { type: "text", placeholder: "reason", "class": "reason" });
        reason.value = (state.decisions[row.expense_id] && state.decisions[row.expense_id].reason) || "";
        reason.addEventListener("change", function () {
          state.decisions[row.expense_id] = state.decisions[row.expense_id] || { decision: "pending" };
          state.decisions[row.expense_id].reason = reason.value;
          persist();
        });
        decisionCell.appendChild(approve);
        decisionCell.appendChild(reject);
        decisionCell.appendChild(reason);
      } else {
        decisionCell.appendChild(el("span", { "class": "auto" }, ["auto-approved"]));
      }
      tr.appendChild(decisionCell);
      tbody.appendChild(tr);
    });
    applyFilter();
    renderSummary(result);
  }

  function setDecision(id, decision) {
    state.decisions[id] = state.decisions[id] || {};
    state.decisions[id].decision = decision;
    persist();
    var tr = document.querySelector('tr[data-id="' + id + '"]');
    if (tr) { tr.className = tr.className.replace(/decision-\w+/, "decision-" + decision); }
    renderSummary(audited());
    applyFilter();
  }

  function renderSummary(result) {
    var approved = 0, rejected = 0, pending = 0;
    result.rows.forEach(function (row) {
      var d = decisionFor(row);
      if (d === "approved") { approved += row.amountCents; }
      else if (d === "rejected") { rejected += row.amountCents; }
      else { pending += 1; }
    });
    setText("total-claimed", A.formatMoney(result.totals.totalClaimed));
    setText("flagged-amount", A.formatMoney(result.totals.flaggedAmount));
    setText("approved-amount", A.formatMoney(approved));
    setText("rejected-amount", A.formatMoney(rejected));
    setText("pending-count", String(pending));
  }

  function setText(id, text) {
    var node = document.getElementById(id);
    if (node) { node.textContent = text; }
  }

  function applyFilter() {
    var flaggedOnly = state.filter === "flagged";
    Array.prototype.forEach.call(document.querySelectorAll("#rows tr"), function (tr) {
      tr.style.display = (flaggedOnly && tr.classList.contains("clean")) ? "none" : "";
    });
  }

  function parseCSV(text) {
    var lines = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n").filter(function (l) { return l.trim() !== ""; });
    if (!lines.length) { return []; }
    var headers = lines[0].split(",");
    return lines.slice(1).map(function (line) {
      var cells = splitLine(line);
      var obj = {};
      headers.forEach(function (h, i) { obj[h.trim()] = (cells[i] || "").trim(); });
      return obj;
    });
  }

  function splitLine(line) {
    var out = [], current = "", inQuotes = false;
    for (var i = 0; i < line.length; i++) {
      var ch = line.charAt(i);
      if (ch === '"') { inQuotes = !inQuotes; }
      else if (ch === "," && !inQuotes) { out.push(current); current = ""; }
      else { current += ch; }
    }
    out.push(current);
    return out;
  }

  function importCSV(file) {
    var reader = new FileReader();
    reader.onload = function () {
      var rows = parseCSV(String(reader.result));
      if (!rows.length) { return; }
      state.expenses = rows;
      state.decisions = {};
      persist();
      renderTable();
      setText("note", "Imported " + rows.length + " expenses.");
    };
    reader.readAsText(file);
  }

  function renderReport() {
    var result = audited();
    var body = result.rows.map(function (row) {
      return "<tr><td>" + row.expense_id + "</td><td>" + escapeHtml(row.employee) + "</td><td>" + row.category +
        "</td><td class='num'>" + A.formatMoney(row.amountCents) + "</td><td>" +
        (row.flags.length ? row.flags.join(", ") : "clean") + "</td><td>" + decisionFor(row) + "</td></tr>";
    }).join("");
    document.getElementById("report").innerHTML =
      "<h1>Expense audit report</h1><p>" + result.rows.length + " expenses, " +
      result.totals.flaggedCount + " flagged for review.</p>" +
      "<table><thead><tr><th>ID</th><th>Employee</th><th>Category</th><th>Amount</th><th>Flags</th><th>Decision</th></tr></thead><tbody>" +
      body + "</tbody></table><p>Total claimed " + A.formatMoney(result.totals.totalClaimed) +
      ", flagged " + A.formatMoney(result.totals.flaggedAmount) + ".</p>";
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    load();
    document.getElementById("filter").addEventListener("change", function (e) {
      state.filter = e.target.checked ? "flagged" : "all";
      applyFilter();
    });
    document.getElementById("import").addEventListener("change", function (e) {
      if (e.target.files && e.target.files[0]) { importCSV(e.target.files[0]); e.target.value = ""; }
    });
    document.getElementById("reset").addEventListener("click", function () {
      state.expenses = window.EXPENSE_SAMPLE.expenses.map(clone);
      state.decisions = {};
      persist();
      renderTable();
      setText("note", "Reset to the sample expenses.");
    });
    document.getElementById("print").addEventListener("click", function () { renderReport(); window.print(); });
    renderTable();
  });
})();
