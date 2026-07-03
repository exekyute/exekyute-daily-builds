/* Expense audit logic for the review app.
 *
 * Pure functions: validate an expense, flag it against the policy, and total a
 * run, with no DOM access. The interface in ui.js wires these to the review
 * queue; the test harness in tests.js checks them. The logic mirrors the Python
 * auditor in 01 to the cent, with money held in integer cents.
 *
 * Runs in the browser (attaches ExpenseAudit to the window) and under Node (it
 * exports the same object), so the tests run in either place.
 */
(function (global) {
  "use strict";

  var MILEAGE = "Mileage";
  var YES_NO = { yes: true, no: false };

  function toCents(value) {
    var text = String(value).trim();
    var negative = text.charAt(0) === "-";
    if (negative) { text = text.slice(1); }
    var parts = text.split(".");
    var whole = parts[0] === "" ? 0 : parseInt(parts[0], 10);
    var fraction = (parts[1] || "").slice(0, 3);
    while (fraction.length < 3) { fraction += "0"; }
    var thousandths = parseInt(fraction, 10);
    var cents = whole * 100 + Math.floor(thousandths / 10);
    if (thousandths % 10 >= 5) { cents += 1; }
    return negative ? -cents : cents;
  }

  function formatMoney(cents) {
    return (cents / 100).toLocaleString("en-CA", { style: "currency", currency: "CAD" });
  }

  function buildPolicy(raw) {
    var caps = {};
    Object.keys(raw.caps || {}).forEach(function (cat) { caps[cat] = toCents(raw.caps[cat]); });
    return {
      mileageRateCents: toCents(raw.mileage_rate),
      receiptThresholdCents: toCents(raw.receipt_threshold),
      caps: caps,
    };
  }

  function allowedCategories(policy) {
    return Object.keys(policy.caps).concat([MILEAGE]);
  }

  function validateExpense(raw, policy) {
    var id = String(raw.expense_id || "").trim() || "(missing id)";
    var label = "Expense " + id;
    var required = ["expense_id", "date", "employee", "category", "amount", "receipt"];
    for (var i = 0; i < required.length; i++) {
      if (String(raw[required[i]] === undefined ? "" : raw[required[i]]).trim() === "") {
        return { ok: false, error: label + ": missing " + required[i] };
      }
    }
    var category = String(raw.category).trim();
    if (allowedCategories(policy).indexOf(category) === -1) {
      return { ok: false, error: label + ": category " + category + " has no policy" };
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(raw.date).trim())) {
      return { ok: false, error: label + ": date must be YYYY-MM-DD" };
    }
    var amountCents = toCents(raw.amount);
    if (amountCents <= 0) { return { ok: false, error: label + ": amount must be above zero" }; }
    var kmText = String(raw.km === undefined ? "" : raw.km).trim();
    var km = kmText === "" ? 0 : Number(kmText);
    if (!(km >= 0)) { return { ok: false, error: label + ": km cannot be negative" }; }
    if (category === MILEAGE && km <= 0) {
      return { ok: false, error: label + ": a mileage claim needs kilometres above zero" };
    }
    var receiptText = String(raw.receipt).trim().toLowerCase();
    if (!(receiptText in YES_NO)) { return { ok: false, error: label + ": receipt must be yes or no" }; }
    return {
      ok: true,
      value: {
        expense_id: id, date: String(raw.date).trim(), employee: String(raw.employee).trim(),
        category: category, amountCents: amountCents, km: km, receipt: YES_NO[receiptText],
      },
    };
  }

  function mileageAmountCents(km, rateCents) {
    return Math.round(km * rateCents);
  }

  function computedAmountCents(expense, policy) {
    return expense.category === MILEAGE
      ? mileageAmountCents(expense.km, policy.mileageRateCents)
      : expense.amountCents;
  }

  function duplicateKeys(expenses) {
    var counts = {};
    expenses.forEach(function (e) {
      var key = [e.employee, e.date, e.category, e.amountCents].join("|");
      counts[key] = (counts[key] || 0) + 1;
    });
    var dup = {};
    Object.keys(counts).forEach(function (k) { if (counts[k] > 1) { dup[k] = true; } });
    return dup;
  }

  function flagsFor(expense, policy, dupKeys) {
    var flags = [];
    if (expense.category === MILEAGE) {
      if (expense.amountCents !== mileageAmountCents(expense.km, policy.mileageRateCents)) {
        flags.push("MILEAGE_MISMATCH");
      }
    } else {
      var cap = policy.caps[expense.category];
      if (cap !== undefined && expense.amountCents > cap) { flags.push("OVER_CAP"); }
      if (expense.amountCents > policy.receiptThresholdCents && !expense.receipt) { flags.push("NO_RECEIPT"); }
    }
    var key = [expense.employee, expense.date, expense.category, expense.amountCents].join("|");
    if (dupKeys[key]) { flags.push("DUPLICATE"); }
    return flags;
  }

  function auditAll(expenses, policy) {
    var dupKeys = duplicateKeys(expenses);
    var rows = expenses.map(function (e) {
      var flags = flagsFor(e, policy, dupKeys);
      return {
        expense_id: e.expense_id, date: e.date, employee: e.employee, category: e.category,
        amountCents: e.amountCents, km: e.km, receipt: e.receipt,
        computedCents: computedAmountCents(e, policy), flags: flags,
        status: flags.length ? "Flagged" : "Approved",
      };
    });
    var flagged = rows.filter(function (r) { return r.flags.length; });
    function sum(list) { return list.reduce(function (a, r) { return a + r.amountCents; }, 0); }
    var totals = {
      totalClaimed: sum(rows),
      flaggedAmount: sum(flagged),
      approvedAmount: sum(rows.filter(function (r) { return !r.flags.length; })),
      flaggedCount: flagged.length,
      approvedCount: rows.length - flagged.length,
      overCapCount: rows.filter(function (r) { return r.flags.indexOf("OVER_CAP") !== -1; }).length,
      noReceiptCount: rows.filter(function (r) { return r.flags.indexOf("NO_RECEIPT") !== -1; }).length,
      duplicateCount: rows.filter(function (r) { return r.flags.indexOf("DUPLICATE") !== -1; }).length,
      mileageMismatchCount: rows.filter(function (r) { return r.flags.indexOf("MILEAGE_MISMATCH") !== -1; }).length,
    };
    return { rows: rows, totals: totals };
  }

  var api = {
    toCents: toCents, formatMoney: formatMoney, buildPolicy: buildPolicy,
    validateExpense: validateExpense, mileageAmountCents: mileageAmountCents,
    computedAmountCents: computedAmountCents, duplicateKeys: duplicateKeys,
    flagsFor: flagsFor, auditAll: auditAll,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.ExpenseAudit = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
