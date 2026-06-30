/* Page wiring for the license manager.
 *
 * Holds the list of subscriptions, renders the editable table, recomputes the
 * derived numbers and totals as rows change, and keeps the list in localStorage
 * so edits survive a refresh. All of the arithmetic lives in subscriptions.js;
 * this file only moves values between the page and that logic.
 */
(function () {
  "use strict";

  var L = window.SubLogic;
  var STORAGE_KEY = "license-manager-state-v1";

  var EDITABLE = [
    { key: "sub_id", type: "text", size: 6 },
    { key: "vendor", type: "text", size: 14 },
    { key: "plan", type: "text", size: 10 },
    { key: "plan_type", type: "select", options: ["per_seat", "flat"] },
    { key: "monthly_unit_cost", type: "number", step: "0.01", min: "0" },
    { key: "seats_owned", type: "number", step: "1", min: "1" },
    { key: "seats_used", type: "number", step: "1", min: "0" },
    { key: "renewal_date", type: "date" },
    { key: "auto_renew", type: "select", options: ["yes", "no"] },
  ];

  var state = { subs: [], asOf: todayISO() };

  function todayISO() {
    var d = new Date();
    return d.getUTCFullYear() + "-" + pad(d.getUTCMonth() + 1) + "-" + pad(d.getUTCDate());
  }
  function pad(n) { return (n < 10 ? "0" : "") + n; }

  function load() {
    var stored = null;
    try { stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY)); } catch (e) { stored = null; }
    if (stored && Array.isArray(stored.subs) && stored.subs.length) {
      state.subs = stored.subs;
      state.asOf = stored.asOf || todayISO();
    } else {
      state.subs = window.SAMPLE_SUBSCRIPTIONS.map(clone);
      state.asOf = "2026-06-30";
    }
  }

  function clone(obj) { return JSON.parse(JSON.stringify(obj)); }

  function persist() {
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (e) { /* storage off */ }
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) { Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]); }); }
    (children || []).forEach(function (c) {
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function inputFor(field, value, index) {
    var node;
    if (field.type === "select") {
      node = el("select");
      field.options.forEach(function (opt) {
        var o = el("option", { value: opt }, [opt]);
        if (String(value) === opt) { o.setAttribute("selected", "selected"); }
        node.appendChild(o);
      });
    } else {
      node = el("input", { type: field.type, value: value === undefined ? "" : value });
      if (field.step) { node.setAttribute("step", field.step); }
      if (field.min !== undefined) { node.setAttribute("min", field.min); }
      if (field.size) { node.style.width = (field.size * 8 + 16) + "px"; }
    }
    node.addEventListener("change", function () {
      state.subs[index][field.key] = node.value;
      recomputeRow(index);
      recomputeTotals();
      persist();
    });
    return node;
  }

  function renderTable() {
    var tbody = document.getElementById("rows");
    tbody.innerHTML = "";
    state.subs.forEach(function (raw, index) {
      var tr = el("tr", { "data-index": String(index) });
      EDITABLE.forEach(function (field) {
        tr.appendChild(el("td", null, [inputFor(field, raw[field.key], index)]));
      });
      ["monthly", "annual", "unused", "waste", "util", "renewal", "action"].forEach(function (key) {
        tr.appendChild(el("td", { "class": "derived " + key }));
      });
      var del = el("button", { "class": "link-button", "title": "Remove" }, ["remove"]);
      del.addEventListener("click", function () {
        state.subs.splice(index, 1);
        renderTable();
        recomputeTotals();
        persist();
      });
      tr.appendChild(el("td", null, [del]));
      tbody.appendChild(tr);
    });
    state.subs.forEach(function (_, index) { recomputeRow(index); });
  }

  function recomputeRow(index) {
    var tr = document.querySelector('tr[data-index="' + index + '"]');
    if (!tr) { return; }
    var check = L.validateSub(state.subs[index]);
    var cell = function (name) { return tr.querySelector(".derived." + name); };
    if (!check.ok) {
      tr.classList.add("invalid");
      cell("monthly").textContent = "";
      cell("action").textContent = "";
      cell("renewal").textContent = check.error.replace(/^Subscription [^:]*:\s*/, "");
      cell("renewal").classList.add("error-text");
      ["annual", "unused", "waste", "util"].forEach(function (n) { cell(n).textContent = ""; });
      return;
    }
    tr.classList.remove("invalid");
    cell("renewal").classList.remove("error-text");
    var row = L.subscriptionRow(check.value, state.asOf);
    cell("monthly").textContent = L.formatMoney(row.monthlyCents);
    cell("annual").textContent = L.formatMoney(row.annualCents);
    cell("unused").textContent = row.plan_type === "per_seat" ? String(row.unusedSeats) : "n/a";
    cell("waste").textContent = L.formatMoney(row.annualWasteCents);
    cell("util").textContent = row.utilization === null ? "n/a" : Math.round(row.utilization * 1000) / 10 + "%";
    cell("renewal").textContent = row.renewalStatus + " (" + row.daysToRenewal + "d)";
    cell("renewal").className = "derived renewal status-" + row.renewalStatus.replace(/\s+/g, "-").toLowerCase();
    cell("action").textContent = row.action;
    cell("action").className = "derived action" + (row.action === "OK" ? "" : " flagged");
  }

  function validatedSubs() {
    var out = [];
    state.subs.forEach(function (raw) {
      var check = L.validateSub(raw);
      if (check.ok) { out.push(check.value); }
    });
    return out;
  }

  function recomputeTotals() {
    var summary = L.summarize(validatedSubs(), state.asOf);
    var t = summary.totals;
    setText("total-monthly", L.formatMoney(t.monthlyCents));
    setText("total-annual", L.formatMoney(t.annualCents));
    setText("total-waste", L.formatMoney(t.annualWasteCents));
    setText("count-due", String(t.dueSoonCount));
    setText("count-expired", String(t.expiredCount));
    setText("count-underused", String(t.underusedCount));
    setText("what-if", L.formatMoney(L.whatIfSavingsCents(summary.rows)));
  }

  function setText(id, text) {
    var node = document.getElementById(id);
    if (node) { node.textContent = text; }
  }

  function parseCSV(text) {
    var lines = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n").filter(function (l) { return l.trim() !== ""; });
    if (!lines.length) { return []; }
    var headers = splitLine(lines[0]);
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
      if (ch === '"') {
        if (inQuotes && line.charAt(i + 1) === '"') { current += '"'; i++; } else { inQuotes = !inQuotes; }
      } else if (ch === "," && !inQuotes) {
        out.push(current); current = "";
      } else { current += ch; }
    }
    out.push(current);
    return out;
  }

  function importCSV(file) {
    var reader = new FileReader();
    reader.onload = function () {
      var rows = parseCSV(String(reader.result));
      if (!rows.length) { showNote("That file had no rows."); return; }
      state.subs = rows;
      renderTable();
      recomputeTotals();
      persist();
      showNote("Imported " + rows.length + " subscriptions.");
    };
    reader.readAsText(file);
  }

  function showNote(text) {
    var note = document.getElementById("note");
    note.textContent = text;
    note.style.opacity = "1";
    window.setTimeout(function () { note.style.opacity = "0.0"; }, 4000);
  }

  function addRow() {
    var n = state.subs.length + 1;
    state.subs.push({
      sub_id: "S-" + pad(n), vendor: "", plan: "", plan_type: "per_seat",
      monthly_unit_cost: "", seats_owned: "", seats_used: "", renewal_date: "", auto_renew: "no",
    });
    renderTable();
    recomputeTotals();
    persist();
  }

  function renderReport() {
    var summary = L.summarize(validatedSubs(), state.asOf);
    var rowsHtml = summary.rows.map(function (r) {
      return "<tr><td>" + r.sub_id + "</td><td>" + escapeHtml(r.vendor) + "</td><td>" + escapeHtml(r.plan) +
        "</td><td class='num'>" + L.formatMoney(r.monthlyCents) + "</td><td class='num'>" + L.formatMoney(r.annualCents) +
        "</td><td class='num'>" + L.formatMoney(r.annualWasteCents) + "</td><td>" + r.renewalStatus +
        "</td><td>" + r.action + "</td></tr>";
    }).join("");
    var t = summary.totals;
    document.getElementById("report").innerHTML =
      "<h1>Subscription and license report</h1>" +
      "<p>As of " + state.asOf + ". " + summary.rows.length + " subscriptions.</p>" +
      "<table><thead><tr><th>ID</th><th>Vendor</th><th>Plan</th><th>Monthly</th><th>Annual</th>" +
      "<th>Annual waste</th><th>Renewal</th><th>Action</th></tr></thead><tbody>" + rowsHtml +
      "</tbody><tfoot><tr><th colspan='3'>Total</th><th class='num'>" + L.formatMoney(t.monthlyCents) +
      "</th><th class='num'>" + L.formatMoney(t.annualCents) + "</th><th class='num'>" + L.formatMoney(t.annualWasteCents) +
      "</th><th colspan='2'></th></tr></tfoot></table>" +
      "<p>Renewals due soon: " + t.dueSoonCount + ". Expired: " + t.expiredCount +
      ". Underused: " + t.underusedCount + ". Annual savings if right-sized: " +
      L.formatMoney(L.whatIfSavingsCents(summary.rows)) + ".</p>";
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function wireControls() {
    document.getElementById("add").addEventListener("click", addRow);
    document.getElementById("reset").addEventListener("click", function () {
      state.subs = window.SAMPLE_SUBSCRIPTIONS.map(clone);
      state.asOf = "2026-06-30";
      document.getElementById("asof").value = state.asOf;
      renderTable();
      recomputeTotals();
      persist();
      showNote("Reset to the sample portfolio.");
    });
    document.getElementById("import").addEventListener("change", function (e) {
      if (e.target.files && e.target.files[0]) { importCSV(e.target.files[0]); e.target.value = ""; }
    });
    var asof = document.getElementById("asof");
    asof.value = state.asOf;
    asof.addEventListener("change", function () {
      state.asOf = asof.value || todayISO();
      state.subs.forEach(function (_, i) { recomputeRow(i); });
      recomputeTotals();
      persist();
    });
    document.getElementById("print").addEventListener("click", function () {
      renderReport();
      window.print();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    load();
    wireControls();
    renderTable();
    recomputeTotals();
  });
})();
