/*
 * validator_logic.js
 *
 * Pure business logic for the Comp Plan Rule Validator. No DOM access and no
 * browser APIs, so every rule can be exercised directly from tests.html. The
 * page script (app.js) reads the plan from the form or from a file and passes
 * it here.
 *
 * This is the formal home of the plan rules. It checks the same plan shape the
 * Tiered Commission Calculator consumes, so a plan that passes here is safe to
 * pay against there. Each problem is returned as a finding with a severity, a
 * code, a location, and a plain message. A plan with no error findings is
 * reported as approved.
 */
var ValidatorLogic = (function () {
  "use strict";

  function isNumber(value) {
    return typeof value === "number"
      ? isFinite(value)
      : value !== null && value !== undefined && String(value).trim() !== "" && isFinite(Number(value));
  }

  function num(value) {
    return Number(value);
  }

  function labelFor(tier, index) {
    return tier && tier.label ? tier.label : "Tier " + (index + 1);
  }

  // Validate a comp plan. Returns:
  //   { approved: boolean, findings: [ { severity, code, location, message } ] }
  // severity is "error" or "warning". approved is true when there are no error
  // findings.
  function validate(plan) {
    var findings = [];

    function add(severity, code, location, message) {
      findings.push({ severity: severity, code: code, location: location, message: message });
    }

    if (!plan || typeof plan !== "object") {
      add("error", "no-plan", "Plan", "No plan was provided.");
      return finish(findings);
    }

    // Plan-level fields.
    if (!isNumber(plan.quota)) {
      add("error", "quota", "Plan", "Quota is missing or not a number.");
    } else if (num(plan.quota) <= 0) {
      add("error", "quota", "Plan", "Quota must be greater than 0.");
    }

    if (!isNumber(plan.accelerator)) {
      add("error", "accelerator", "Plan", "Accelerator is missing or not a number.");
    } else if (num(plan.accelerator) < 1) {
      add("error", "accelerator", "Plan", "Accelerator must be 1.0 or more, otherwise it would reduce pay above quota.");
    }

    if (!Array.isArray(plan.tiers) || plan.tiers.length === 0) {
      add("error", "no-tiers", "Plan", "The plan has no tiers.");
      return finish(findings);
    }

    var i;
    var seenLabels = {};

    // Per-tier field checks.
    for (i = 0; i < plan.tiers.length; i++) {
      var tier = plan.tiers[i];
      var loc = labelFor(tier, i);
      var isTop = i === plan.tiers.length - 1;

      if (tier.label) {
        var key = String(tier.label).toLowerCase();
        if (Object.prototype.hasOwnProperty.call(seenLabels, key)) {
          add("error", "duplicate-label", loc, "Tier label '" + tier.label + "' is used more than once.");
        }
        seenLabels[key] = true;
      }

      if (!isNumber(tier.from)) {
        add("error", "tier-from", loc, "'from' is missing or not a number.");
      } else if (num(tier.from) < 0) {
        add("error", "tier-from", loc, "'from' cannot be negative.");
      }

      var hasTo = tier.to !== null && tier.to !== undefined && String(tier.to).trim() !== "";
      if (isTop) {
        if (hasTo) {
          if (!isNumber(tier.to)) {
            add("error", "tier-to", loc, "'to' must be a number or left open.");
          } else if (num(tier.to) <= num(tier.from)) {
            add("error", "tier-order", loc, "'to' must be greater than 'from'.");
          } else {
            add("warning", "top-tier-open", loc, "The top tier has an upper bound, so revenue above " + tier.to + " would earn nothing. Leave it open unless that is intended.");
          }
        }
      } else {
        if (!hasTo) {
          add("error", "tier-to", loc, "Only the top tier may be open ended.");
        } else if (!isNumber(tier.to)) {
          add("error", "tier-to", loc, "'to' is not a number.");
        } else if (num(tier.to) <= num(tier.from)) {
          add("error", "tier-order", loc, "'to' must be greater than 'from'.");
        }
      }

      if (!isNumber(tier.rate)) {
        add("error", "tier-rate", loc, "Rate is missing or not a number.");
      } else if (num(tier.rate) <= 0) {
        add("error", "tier-rate", loc, "Rate must be greater than 0.");
      }
    }

    // First tier should start at 0 so the bottom of the range is covered.
    var first = plan.tiers[0];
    if (isNumber(first.from) && num(first.from) !== 0) {
      add("error", "first-tier-start", labelFor(first, 0), "The first tier should start at 0. Revenue from 0 to " + first.from + " is uncovered.");
    }

    // Thresholds must run in order with no gap and no overlap.
    for (i = 0; i < plan.tiers.length - 1; i++) {
      var current = plan.tiers[i];
      var next = plan.tiers[i + 1];
      if (!isNumber(current.to) || !isNumber(next.from)) {
        continue; // already reported above
      }
      var currentTo = num(current.to);
      var nextFrom = num(next.from);
      var pair = labelFor(current, i) + " to " + labelFor(next, i + 1);
      if (nextFrom > currentTo) {
        add("error", "gap", pair, "Gap: revenue from " + currentTo + " to " + nextFrom + " is not covered by any tier.");
      } else if (nextFrom < currentTo) {
        add("error", "overlap", pair, "Overlap: both tiers cover revenue around " + nextFrom + ".");
      }
    }

    return finish(findings);
  }

  function finish(findings) {
    var hasError = findings.some(function (f) { return f.severity === "error"; });
    return { approved: !hasError, findings: findings };
  }

  function countBySeverity(findings, severity) {
    return findings.filter(function (f) { return f.severity === severity; }).length;
  }

  // Parse plan JSON text into a plan object. Returns { ok, plan } or { ok, error }.
  function parsePlanJson(text) {
    var data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      return { ok: false, error: "File is not valid JSON: " + e.message };
    }
    if (!data || typeof data !== "object") {
      return { ok: false, error: "File does not contain a plan object." };
    }
    return { ok: true, plan: data };
  }

  return {
    validate: validate,
    countBySeverity: countBySeverity,
    parsePlanJson: parsePlanJson
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = ValidatorLogic;
}
