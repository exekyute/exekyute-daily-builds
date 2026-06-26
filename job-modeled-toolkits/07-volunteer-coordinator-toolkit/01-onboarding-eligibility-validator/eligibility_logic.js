/*
 * eligibility_logic.js
 *
 * Pure business logic for the Onboarding Eligibility Validator. No DOM access
 * and no browser APIs, so every rule can be exercised directly from tests.html.
 * The page script (app.js) reads volunteers from the form or from a file and
 * passes them here.
 *
 * This is the formal home of the onboarding rules. A volunteer is cleared only
 * when every requirement is met: of-age, a passed and unexpired background
 * check, every required training complete, and a signed unexpired waiver. The
 * cleared roster this produces is the same roster the Shift Coverage Planner
 * consumes, so a volunteer cleared here is safe to schedule there.
 *
 * Dates are plain YYYY-MM-DD strings. Durations are whole days. Times are not
 * used here.
 */
var EligibilityLogic = (function () {
  "use strict";

  // Default reference config. The page can override any of these.
  var DEFAULT_CONFIG = {
    as_of_date: "2026-06-01",
    minimum_age: 18,
    required_trainings: ["ORIENT", "SAFETY"],
    background_check_valid_days: 365,
    waiver_valid_days: 365
  };

  // Parse a YYYY-MM-DD string into a UTC Date, or null if it is not a real
  // calendar date. Using UTC keeps the day math free of timezone drift.
  function parseYmd(value) {
    if (typeof value !== "string") {
      return null;
    }
    var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
    if (!match) {
      return null;
    }
    var year = Number(match[1]);
    var month = Number(match[2]);
    var day = Number(match[3]);
    if (month < 1 || month > 12 || day < 1 || day > 31) {
      return null;
    }
    var date = new Date(Date.UTC(year, month - 1, day));
    // Reject dates that rolled over, for example 2026-02-30.
    if (date.getUTCFullYear() !== year ||
        date.getUTCMonth() !== month - 1 ||
        date.getUTCDate() !== day) {
      return null;
    }
    return date;
  }

  // Whole days from the earlier date to the later one (later minus earlier).
  // Returns null if either string is not a real date.
  function daysBetween(fromStr, toStr) {
    var from = parseYmd(fromStr);
    var to = parseYmd(toStr);
    if (!from || !to) {
      return null;
    }
    return Math.round((to.getTime() - from.getTime()) / 86400000);
  }

  // Whole years of age on a reference date, or null if either date is bad.
  function ageOn(dobStr, asOfStr) {
    var dob = parseYmd(dobStr);
    var asOf = parseYmd(asOfStr);
    if (!dob || !asOf) {
      return null;
    }
    var age = asOf.getUTCFullYear() - dob.getUTCFullYear();
    var beforeBirthday =
      asOf.getUTCMonth() < dob.getUTCMonth() ||
      (asOf.getUTCMonth() === dob.getUTCMonth() && asOf.getUTCDate() < dob.getUTCDate());
    if (beforeBirthday) {
      age = age - 1;
    }
    return age;
  }

  function fillConfig(config) {
    var c = config || {};
    return {
      as_of_date: c.as_of_date || DEFAULT_CONFIG.as_of_date,
      minimum_age: c.minimum_age === undefined || c.minimum_age === null || c.minimum_age === ""
        ? DEFAULT_CONFIG.minimum_age : Number(c.minimum_age),
      required_trainings: Array.isArray(c.required_trainings)
        ? c.required_trainings : DEFAULT_CONFIG.required_trainings,
      background_check_valid_days: c.background_check_valid_days === undefined ||
        c.background_check_valid_days === null || c.background_check_valid_days === ""
        ? DEFAULT_CONFIG.background_check_valid_days : Number(c.background_check_valid_days),
      waiver_valid_days: c.waiver_valid_days === undefined ||
        c.waiver_valid_days === null || c.waiver_valid_days === ""
        ? DEFAULT_CONFIG.waiver_valid_days : Number(c.waiver_valid_days)
    };
  }

  // Evaluate one volunteer. Returns:
  //   { id, name, cleared, findings: [ { severity, code, location, message } ] }
  // Every finding here is an "error": each one blocks clearance. A volunteer
  // with no findings is cleared.
  function evaluate(volunteer, config) {
    var c = fillConfig(config);
    var findings = [];
    var v = volunteer || {};
    var who = v.name ? v.name : (v.id ? v.id : "Volunteer");

    function add(code, message) {
      findings.push({ severity: "error", code: code, location: who, message: message });
    }

    if (!v.id || String(v.id).trim() === "") {
      add("missing-id", "Volunteer id is missing.");
    }
    if (!v.name || String(v.name).trim() === "") {
      add("missing-name", "Volunteer name is missing.");
    }

    // Age.
    var age = ageOn(v.date_of_birth, c.as_of_date);
    if (age === null) {
      add("bad-dob", "Date of birth is missing or not a real YYYY-MM-DD date.");
    } else if (age < c.minimum_age) {
      add("under-age", "Volunteer is " + age + " on " + c.as_of_date +
        ", under the minimum age of " + c.minimum_age + ".");
    }

    // Background check.
    var bg = v.background_check;
    if (!bg || !bg.status || bg.status === "none") {
      add("bg-missing", "No background check on file.");
    } else if (bg.status !== "passed") {
      add("bg-not-passed", "Background check status is '" + bg.status + "', not 'passed'.");
    } else {
      var bgDays = daysBetween(bg.date, c.as_of_date);
      if (bgDays === null) {
        add("bg-bad-date", "Background check date is missing or not a real date.");
      } else if (bgDays < 0) {
        add("bg-bad-date", "Background check date " + bg.date + " is after the as-of date.");
      } else if (bgDays > c.background_check_valid_days) {
        add("bg-expired", "Background check from " + bg.date + " is older than " +
          c.background_check_valid_days + " days as of " + c.as_of_date + ".");
      }
    }

    // Required training.
    var done = Array.isArray(v.trainings_completed) ? v.trainings_completed : [];
    c.required_trainings.forEach(function (code) {
      if (done.indexOf(code) === -1) {
        add("training-missing", "Required training '" + code + "' is not complete.");
      }
    });

    // Waiver.
    var waiver = v.waiver_signed_date;
    if (!waiver || String(waiver).trim() === "") {
      add("waiver-missing", "No signed waiver on file.");
    } else {
      var waiverDays = daysBetween(waiver, c.as_of_date);
      if (waiverDays === null) {
        add("waiver-bad-date", "Waiver date is not a real date.");
      } else if (waiverDays < 0) {
        add("waiver-bad-date", "Waiver date " + waiver + " is after the as-of date.");
      } else if (waiverDays > c.waiver_valid_days) {
        add("waiver-expired", "Waiver from " + waiver + " is older than " +
          c.waiver_valid_days + " days as of " + c.as_of_date + ".");
      }
    }

    return {
      id: v.id || "",
      name: v.name || "",
      cleared: findings.length === 0,
      findings: findings
    };
  }

  // Evaluate a whole roster. Returns:
  //   { results: [ ...evaluate output ], summary: { total, clearedCount, blockedCount } }
  // A duplicate id is flagged on the second and later volunteers that use it,
  // and blocks those volunteers.
  function evaluateRoster(volunteers, config) {
    var list = Array.isArray(volunteers) ? volunteers : [];
    var seen = {};
    var results = list.map(function (v) {
      var result = evaluate(v, config);
      var key = v && v.id ? String(v.id).trim().toLowerCase() : "";
      if (key !== "") {
        if (Object.prototype.hasOwnProperty.call(seen, key)) {
          result.findings.push({
            severity: "error",
            code: "duplicate-id",
            location: result.name || result.id,
            message: "Volunteer id '" + v.id + "' is used more than once."
          });
          result.cleared = false;
        }
        seen[key] = true;
      }
      return result;
    });

    var clearedCount = results.filter(function (r) { return r.cleared; }).length;
    return {
      results: results,
      summary: {
        total: results.length,
        clearedCount: clearedCount,
        blockedCount: results.length - clearedCount
      }
    };
  }

  // Build the cleared roster the Shift Coverage Planner consumes:
  //   [ { id, name, cleared } ]
  function toClearedRoster(rosterResult) {
    return rosterResult.results.map(function (r) {
      return { id: r.id, name: r.name, cleared: r.cleared };
    });
  }

  // Parse volunteers JSON text. Accepts either a bare array of volunteers or an
  // object with a "volunteers" array and an optional "config". Returns
  // { ok, volunteers, config } or { ok, error }.
  function parseVolunteersJson(text) {
    var data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      return { ok: false, error: "File is not valid JSON: " + e.message };
    }
    if (Array.isArray(data)) {
      return { ok: true, volunteers: data, config: null };
    }
    if (data && typeof data === "object" && Array.isArray(data.volunteers)) {
      return { ok: true, volunteers: data.volunteers, config: data.config || null };
    }
    return { ok: false, error: "File does not contain a volunteers array." };
  }

  return {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    parseYmd: parseYmd,
    daysBetween: daysBetween,
    ageOn: ageOn,
    evaluate: evaluate,
    evaluateRoster: evaluateRoster,
    toClearedRoster: toClearedRoster,
    parseVolunteersJson: parseVolunteersJson
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = EligibilityLogic;
}
