/*
 * commission_logic.js
 *
 * Pure business logic for the Tiered Commission Calculator. No DOM access and
 * no browser APIs, so every function here can be exercised directly from
 * tests.html. The page script (app.js) is the only place that touches the DOM.
 *
 * Money is handled in integer cents. Rates are converted to basis points
 * (5% becomes 500) and the accelerator to thousandths (1.5 becomes 1500) so
 * that every payout figure is computed with integer arithmetic and rounded
 * exactly once per portion. Output strings are built with Intl.NumberFormat so
 * amounts never show floating point artifacts.
 */
var CommissionLogic = (function () {
  "use strict";

  var currencyFormatter = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD"
  });

  var percentFormatter = new Intl.NumberFormat("en-US", {
    style: "percent",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2
  });

  // --- parsing helpers ------------------------------------------------------

  // Turn a dollar amount (string or number) into an integer number of cents.
  // Returns { ok: true, cents } or { ok: false, error }. Rejects anything that
  // is not a finite, non-negative number once stripped of $ and thousands
  // separators.
  function parseDollarsToCents(value) {
    if (value === null || value === undefined) {
      return { ok: false, error: "value is missing" };
    }
    var text = String(value).trim().replace(/[$,\s]/g, "");
    if (text === "") {
      return { ok: false, error: "value is empty" };
    }
    if (!/^-?\d+(\.\d+)?$/.test(text)) {
      return { ok: false, error: "value is not a number" };
    }
    var amount = Number(text);
    if (!isFinite(amount)) {
      return { ok: false, error: "value is not a finite number" };
    }
    if (amount < 0) {
      return { ok: false, error: "value cannot be negative" };
    }
    // Round to the nearest cent to absorb a stray third decimal place.
    return { ok: true, cents: Math.round(amount * 100) };
  }

  // Turn a percent (e.g. 5 or 7.5) into integer basis points (500 or 750).
  function parseRateToBasisPoints(value) {
    if (value === null || value === undefined || String(value).trim() === "") {
      return { ok: false, error: "rate is missing" };
    }
    var amount = Number(String(value).trim());
    if (!isFinite(amount)) {
      return { ok: false, error: "rate is not a number" };
    }
    return { ok: true, bp: Math.round(amount * 100) };
  }

  // --- validation -----------------------------------------------------------

  // Guard the plan before any money math runs. Returns an array of plain
  // problem strings; an empty array means the plan is safe to calculate with.
  // This is the calculator's own guard. The Comp Plan Rule Validator (tool 3)
  // holds the full, formal version of these same rules.
  function validatePlan(plan) {
    var problems = [];

    if (!plan || typeof plan !== "object") {
      return ["Plan is missing or not an object."];
    }
    if (!Array.isArray(plan.tiers) || plan.tiers.length === 0) {
      problems.push("Plan has no tiers.");
      return problems;
    }

    var quota = Number(plan.quota);
    if (!isFinite(quota) || quota <= 0) {
      problems.push("Quota must be a number greater than 0.");
    }

    var accelerator = Number(plan.accelerator);
    if (!isFinite(accelerator) || accelerator < 1) {
      problems.push("Accelerator must be a number of 1.0 or more.");
    }

    var i;
    for (i = 0; i < plan.tiers.length; i++) {
      var tier = plan.tiers[i];
      var label = tier && tier.label ? tier.label : "Tier " + (i + 1);

      var from = Number(tier.from);
      if (!isFinite(from) || from < 0) {
        problems.push(label + ": 'from' must be a number of 0 or more.");
      }

      var isTop = i === plan.tiers.length - 1;
      if (isTop) {
        if (tier.to !== null && tier.to !== undefined && tier.to !== "") {
          // A closed top tier is allowed but means revenue above it earns
          // nothing, so flag it as a problem the analyst should confirm.
          var topTo = Number(tier.to);
          if (!isFinite(topTo)) {
            problems.push(label + ": top tier 'to' must be a number or open (null).");
          } else if (topTo <= from) {
            problems.push(label + ": 'to' must be greater than 'from'.");
          }
        }
      } else {
        var to = Number(tier.to);
        if (tier.to === null || tier.to === undefined || tier.to === "") {
          problems.push(label + ": only the top tier may be open ended.");
        } else if (!isFinite(to)) {
          problems.push(label + ": 'to' must be a number.");
        } else if (to <= from) {
          problems.push(label + ": 'to' must be greater than 'from'.");
        }
      }

      var rate = Number(tier.rate);
      if (!isFinite(rate) || rate <= 0) {
        problems.push(label + ": rate must be greater than 0.");
      }
    }

    // Thresholds must run in order with no gap and no overlap.
    for (i = 0; i < plan.tiers.length - 1; i++) {
      var current = plan.tiers[i];
      var next = plan.tiers[i + 1];
      var currentTo = Number(current.to);
      var nextFrom = Number(next.from);
      if (!isFinite(currentTo) || !isFinite(nextFrom)) {
        continue; // already reported above
      }
      if (nextFrom > currentTo) {
        problems.push(
          "Gap between " + tierLabel(plan, i) + " and " + tierLabel(plan, i + 1) +
          ": revenue from " + currentTo + " to " + nextFrom + " is uncovered."
        );
      } else if (nextFrom < currentTo) {
        problems.push(
          "Overlap between " + tierLabel(plan, i) + " and " + tierLabel(plan, i + 1) +
          ": both cover revenue around " + nextFrom + "."
        );
      }
    }

    return problems;
  }

  function tierLabel(plan, index) {
    var tier = plan.tiers[index];
    return tier && tier.label ? tier.label : "Tier " + (index + 1);
  }

  // Validate the revenue field on its own so the page can report a bad revenue
  // separately from a bad plan.
  function validateRevenue(revenueInput) {
    var parsed = parseDollarsToCents(revenueInput);
    if (!parsed.ok) {
      return ["Revenue " + parsed.error + "."];
    }
    return [];
  }

  // --- core calculation -----------------------------------------------------

  // Compute the payout for one revenue figure against a validated plan.
  // Returns a breakdown object. Assumes validatePlan and validateRevenue have
  // already passed; callers should check those first.
  function computePayout(plan, revenueInput) {
    var revenueCents = parseDollarsToCents(revenueInput).cents;
    var quotaCents = Math.round(Number(plan.quota) * 100);
    var accelMilli = Math.round(Number(plan.accelerator) * 1000);

    var rows = [];
    var totalCents = 0;
    var i;

    for (i = 0; i < plan.tiers.length; i++) {
      var tier = plan.tiers[i];
      var fromCents = Math.round(Number(tier.from) * 100);
      var toCents =
        tier.to === null || tier.to === undefined || tier.to === ""
          ? Infinity
          : Math.round(Number(tier.to) * 100);
      var bp = Math.round(Number(tier.rate) * 100);

      // The slice of revenue that falls inside this tier band.
      var bandHigh = Math.min(revenueCents, toCents);
      var bandRevenue = Math.max(0, bandHigh - fromCents);

      // Split the band at the quota line. Anything at or below quota earns the
      // base rate; anything above quota earns the base rate times accelerator.
      var belowPortion = Math.max(0, Math.min(bandHigh, quotaCents) - fromCents);
      if (belowPortion > bandRevenue) {
        belowPortion = bandRevenue;
      }
      var abovePortion = bandRevenue - belowPortion;

      var belowCommission = Math.round((belowPortion * bp) / 10000);
      var aboveCommission = Math.round(
        (abovePortion * bp * accelMilli) / (10000 * 1000)
      );
      var tierTotal = belowCommission + aboveCommission;
      totalCents += tierTotal;

      rows.push({
        label: tier.label || "Tier " + (i + 1),
        fromCents: fromCents,
        toCents: toCents,
        rateBp: bp,
        bandRevenueCents: bandRevenue,
        belowPortionCents: belowPortion,
        abovePortionCents: abovePortion,
        belowCommissionCents: belowCommission,
        aboveCommissionCents: aboveCommission,
        tierTotalCents: tierTotal,
        accelerated: abovePortion > 0
      });
    }

    return {
      revenueCents: revenueCents,
      quotaCents: quotaCents,
      accelMilli: accelMilli,
      rows: rows,
      totalCents: totalCents
    };
  }

  // --- formatting -----------------------------------------------------------

  function formatCents(cents) {
    if (cents === Infinity) {
      return "and up";
    }
    return currencyFormatter.format(cents / 100);
  }

  function formatBasisPoints(bp) {
    return percentFormatter.format(bp / 10000);
  }

  function formatAccelerator(accelMilli) {
    return (accelMilli / 1000).toFixed(2) + "x";
  }

  // --- JSON plan loading ----------------------------------------------------

  // Parse plan JSON text (from a file the user picked) into a plan object.
  // Returns { ok: true, plan } or { ok: false, error }.
  function parsePlanJson(text) {
    var data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      return { ok: false, error: "File is not valid JSON: " + e.message };
    }
    if (!data || typeof data !== "object" || !Array.isArray(data.tiers)) {
      return { ok: false, error: "JSON does not look like a comp plan (no tiers array)." };
    }
    return { ok: true, plan: data };
  }

  return {
    parseDollarsToCents: parseDollarsToCents,
    parseRateToBasisPoints: parseRateToBasisPoints,
    validatePlan: validatePlan,
    validateRevenue: validateRevenue,
    computePayout: computePayout,
    formatCents: formatCents,
    formatBasisPoints: formatBasisPoints,
    formatAccelerator: formatAccelerator,
    parsePlanJson: parsePlanJson
  };
})();

// Make the module usable from a CommonJS test runner as well as the browser,
// without requiring any build step in the browser.
if (typeof module !== "undefined" && module.exports) {
  module.exports = CommissionLogic;
}
