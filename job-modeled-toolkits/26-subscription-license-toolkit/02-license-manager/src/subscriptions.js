/* Subscription and license logic for the license manager app.
 *
 * Pure functions: each takes plain values and returns plain values, with no DOM
 * access. The interface in ui.js wires these to the page; the test harness in
 * tests.js checks them. The math mirrors the Python ledger in 01 to the cent.
 *
 * Money is held in integer cents so amounts never pick up floating-point dust,
 * the same way the Python tool uses Decimal. The file runs in the browser (it
 * attaches SubLogic to the window) and under Node (it exports the same object),
 * so the tests can run in either place.
 */
(function (global) {
  "use strict";

  var UNDERUSED_BELOW = 0.70;
  var DUE_SOON_DAYS = 30;
  var UPCOMING_DAYS = 90;
  var PLAN_TYPES = ["per_seat", "flat"];
  var DAY_MS = 24 * 60 * 60 * 1000;

  // Parse a money string or number into integer cents, rounded half up.
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
    return (cents / 100).toLocaleString("en-CA", {
      style: "currency", currency: "CAD",
    });
  }

  function monthlyCostCents(planType, unitCents, seatsOwned) {
    return planType === "per_seat" ? unitCents * seatsOwned : unitCents;
  }

  function unusedSeats(planType, seatsOwned, seatsUsed) {
    return planType === "per_seat" ? seatsOwned - seatsUsed : 0;
  }

  function monthlyWasteCents(planType, unitCents, seatsOwned, seatsUsed) {
    return planType === "per_seat" ? unitCents * unusedSeats(planType, seatsOwned, seatsUsed) : 0;
  }

  // Share of owned seats in use, rounded to four places. null for a flat plan.
  function utilization(planType, seatsOwned, seatsUsed) {
    if (planType !== "per_seat") { return null; }
    if (seatsOwned <= 0) { return 0; }
    return Math.round((seatsUsed / seatsOwned) * 10000) / 10000;
  }

  // Whole days from asOf to renewalDate, both ISO dates, measured in UTC so a
  // daylight-saving change cannot shift the count.
  function daysToRenewal(asOfISO, renewalISO) {
    var a = asOfISO.split("-");
    var r = renewalISO.split("-");
    var asOf = Date.UTC(+a[0], +a[1] - 1, +a[2]);
    var renewal = Date.UTC(+r[0], +r[1] - 1, +r[2]);
    return Math.round((renewal - asOf) / DAY_MS);
  }

  function renewalStatus(days) {
    if (days < 0) { return "Expired"; }
    if (days <= DUE_SOON_DAYS) { return "Due soon"; }
    if (days <= UPCOMING_DAYS) { return "Upcoming"; }
    return "Current";
  }

  function action(planType, days, autoRenew, util) {
    if (days < 0) { return "Expired, review"; }
    var renewsSoon = autoRenew && days <= DUE_SOON_DAYS;
    var underused = util !== null && util < UNDERUSED_BELOW;
    if (renewsSoon && underused) { return "Auto-renews soon, underused"; }
    if (renewsSoon) { return "Auto-renews soon"; }
    if (underused) { return "Underused"; }
    return "OK";
  }

  // Validate one raw subscription. Returns {ok:true, value} or {ok:false, error}.
  function validateSub(raw) {
    var id = String(raw.sub_id || "").trim() || "(missing id)";
    var label = "Subscription " + id;
    var required = ["sub_id", "vendor", "plan", "plan_type", "monthly_unit_cost",
      "seats_owned", "seats_used", "renewal_date", "auto_renew"];
    for (var i = 0; i < required.length; i++) {
      if (String(raw[required[i]] === undefined ? "" : raw[required[i]]).trim() === "") {
        return { ok: false, error: label + ": missing " + required[i] };
      }
    }
    var planType = String(raw.plan_type).trim();
    if (PLAN_TYPES.indexOf(planType) === -1) {
      return { ok: false, error: label + ": plan_type must be per_seat or flat" };
    }
    var unitCents = toCents(raw.monthly_unit_cost);
    if (unitCents < 0) { return { ok: false, error: label + ": monthly_unit_cost cannot be negative" }; }
    var seatsOwned = parseInt(String(raw.seats_owned).trim(), 10);
    var seatsUsed = parseInt(String(raw.seats_used).trim(), 10);
    if (!Number.isInteger(seatsOwned) || seatsOwned <= 0) {
      return { ok: false, error: label + ": seats_owned must be a whole number above zero" };
    }
    if (!Number.isInteger(seatsUsed) || seatsUsed < 0) {
      return { ok: false, error: label + ": seats_used must be zero or more" };
    }
    if (seatsUsed > seatsOwned) {
      return { ok: false, error: label + ": seats_used (" + seatsUsed + ") cannot exceed seats_owned (" + seatsOwned + ")" };
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(raw.renewal_date).trim())) {
      return { ok: false, error: label + ": renewal_date must be YYYY-MM-DD" };
    }
    var autoText = String(raw.auto_renew).trim().toLowerCase();
    if (autoText !== "yes" && autoText !== "no") {
      return { ok: false, error: label + ": auto_renew must be yes or no" };
    }
    return {
      ok: true,
      value: {
        sub_id: id, vendor: String(raw.vendor).trim(), plan: String(raw.plan).trim(),
        plan_type: planType, unitCents: unitCents, seats_owned: seatsOwned,
        seats_used: seatsUsed, renewal_date: String(raw.renewal_date).trim(),
        auto_renew: autoText === "yes",
      },
    };
  }

  // Build the derived row for one validated subscription value.
  function subscriptionRow(sub, asOfISO) {
    var mc = monthlyCostCents(sub.plan_type, sub.unitCents, sub.seats_owned);
    var mw = monthlyWasteCents(sub.plan_type, sub.unitCents, sub.seats_owned, sub.seats_used);
    var util = utilization(sub.plan_type, sub.seats_owned, sub.seats_used);
    var days = daysToRenewal(asOfISO, sub.renewal_date);
    return {
      sub_id: sub.sub_id, vendor: sub.vendor, plan: sub.plan, plan_type: sub.plan_type,
      unitCents: sub.unitCents, seats_owned: sub.seats_owned, seats_used: sub.seats_used,
      monthlyCents: mc, annualCents: mc * 12,
      unusedSeats: unusedSeats(sub.plan_type, sub.seats_owned, sub.seats_used),
      monthlyWasteCents: mw, annualWasteCents: mw * 12,
      utilization: util, renewal_date: sub.renewal_date, daysToRenewal: days,
      renewalStatus: renewalStatus(days), auto_renew: sub.auto_renew,
      action: action(sub.plan_type, days, sub.auto_renew, util),
    };
  }

  // Summarize a list of validated subscription values into rows and totals.
  function summarize(subs, asOfISO) {
    var rows = subs.map(function (s) { return subscriptionRow(s, asOfISO); });
    var totals = {
      monthlyCents: 0, annualCents: 0, monthlyWasteCents: 0, annualWasteCents: 0,
      dueSoonCount: 0, expiredCount: 0, underusedCount: 0,
    };
    rows.forEach(function (r) {
      totals.monthlyCents += r.monthlyCents;
      totals.annualCents += r.annualCents;
      totals.monthlyWasteCents += r.monthlyWasteCents;
      totals.annualWasteCents += r.annualWasteCents;
      if (r.renewalStatus === "Due soon") { totals.dueSoonCount += 1; }
      if (r.renewalStatus === "Expired") { totals.expiredCount += 1; }
      if (r.utilization !== null && r.utilization < UNDERUSED_BELOW) { totals.underusedCount += 1; }
    });
    return { rows: rows, totals: totals };
  }

  // Annual savings if every expired plan is dropped and every underused per-seat
  // plan is cut back to the seats actually in use.
  function whatIfSavingsCents(rows) {
    var saved = 0;
    rows.forEach(function (r) {
      if (r.renewalStatus === "Expired") {
        saved += r.annualCents;
      } else if (r.utilization !== null && r.utilization < UNDERUSED_BELOW) {
        saved += r.annualWasteCents;
      }
    });
    return saved;
  }

  var api = {
    toCents: toCents, formatMoney: formatMoney, monthlyCostCents: monthlyCostCents,
    unusedSeats: unusedSeats, monthlyWasteCents: monthlyWasteCents, utilization: utilization,
    daysToRenewal: daysToRenewal, renewalStatus: renewalStatus, action: action,
    validateSub: validateSub, subscriptionRow: subscriptionRow, summarize: summarize,
    whatIfSavingsCents: whatIfSavingsCents,
    UNDERUSED_BELOW: UNDERUSED_BELOW,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.SubLogic = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
