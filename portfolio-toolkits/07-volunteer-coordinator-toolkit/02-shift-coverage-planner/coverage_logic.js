/*
 * coverage_logic.js
 *
 * Pure business logic for the Shift Coverage Planner. No DOM access and no
 * browser APIs, so every rule can be exercised directly from tests.html. The
 * page script (app.js) reads the shifts, the assignments, and the cleared
 * roster from the form or from files and passes them here.
 *
 * Only cleared volunteers count toward coverage. The cleared roster this tool
 * reads is the same file the Onboarding Eligibility Validator produces, so a
 * volunteer blocked there cannot fill a shift here.
 *
 * Times are 24-hour HH:MM and all duration math is in whole minutes from
 * midnight. Shifts are single-day; a shift does not cross midnight. Two shifts
 * overlap on a half-open basis, so 12:00-13:00 and 13:00-14:00 only touch and
 * do not conflict.
 */
var CoverageLogic = (function () {
  "use strict";

  // Minutes from midnight for an HH:MM string, or null if it is not a real
  // 24-hour time.
  function toMinutes(value) {
    if (typeof value !== "string") {
      return null;
    }
    var match = /^(\d{2}):(\d{2})$/.exec(value.trim());
    if (!match) {
      return null;
    }
    var hours = Number(match[1]);
    var minutes = Number(match[2]);
    if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
      return null;
    }
    return hours * 60 + minutes;
  }

  function isCount(value) {
    return value !== null && value !== undefined && String(value).trim() !== "" &&
      isFinite(Number(value)) && Number(value) >= 0 && Number(value) % 1 === 0;
  }

  // Half-open overlap test. Touching ends do not overlap.
  function overlaps(aStart, aEnd, bStart, bEnd) {
    return aStart < bEnd && bStart < aEnd;
  }

  function rosterMapOf(roster) {
    var map = {};
    (Array.isArray(roster) ? roster : []).forEach(function (r) {
      if (r && r.id !== undefined && r.id !== null && String(r.id).trim() !== "") {
        map[String(r.id).trim()] = { name: r.name || String(r.id), cleared: r.cleared === true };
      }
    });
    return map;
  }

  // Validate one shift and attach computed fields. Returns a result object with
  // valid/issue plus startMin/endMin when valid.
  function checkShift(shift) {
    var s = shift || {};
    var result = {
      id: s.id || "",
      role: s.role || "",
      date: s.date || "",
      start: s.start || "",
      end: s.end || "",
      min: s.min,
      max: s.max,
      valid: true,
      issue: "",
      startMin: null,
      endMin: null,
      clearedIds: [],
      clearedNames: [],
      clearedCount: 0,
      status: "ok"
    };

    if (!result.id) {
      result.valid = false;
      result.issue = "Shift id is missing.";
    }
    var startMin = toMinutes(s.start);
    var endMin = toMinutes(s.end);
    if (startMin === null || endMin === null) {
      result.valid = false;
      result.issue = "Start or end time is not a real 24-hour HH:MM time.";
    } else if (endMin <= startMin) {
      result.valid = false;
      result.issue = "End time must be after start time.";
    } else {
      result.startMin = startMin;
      result.endMin = endMin;
    }
    if (!isCount(s.min) || !isCount(s.max)) {
      result.valid = false;
      result.issue = result.issue || "Min and max must be whole numbers of 0 or more.";
    } else if (Number(s.max) < Number(s.min)) {
      result.valid = false;
      result.issue = result.issue || "Max cannot be less than min.";
    }
    return result;
  }

  // Plan coverage across the schedule. Returns:
  //   {
  //     shifts:   [ ...shift result with clearedCount and status ],
  //     conflicts:[ { volunteerId, name, shiftA, shiftB, date } ],
  //     rejected: [ { volunteerId, name, shiftId, reason } ],
  //     summary:  { shiftCount, okCount, understaffed, overstaffed, invalid,
  //                 conflictCount, rejectedCount }
  //   }
  function planCoverage(shifts, assignments, roster) {
    var roster_ = rosterMapOf(roster);
    var shiftResults = (Array.isArray(shifts) ? shifts : []).map(checkShift);

    var byId = {};
    shiftResults.forEach(function (sr) {
      if (sr.id) {
        byId[sr.id] = sr;
      }
    });

    var rejected = [];
    var counted = []; // assignments that count toward coverage
    var seenPairs = {};

    (Array.isArray(assignments) ? assignments : []).forEach(function (a) {
      var shiftId = a && a.shiftId !== undefined ? String(a.shiftId).trim() : "";
      var volunteerId = a && a.volunteerId !== undefined ? String(a.volunteerId).trim() : "";
      var shift = byId[shiftId];
      var vol = roster_[volunteerId];
      var name = vol ? vol.name : volunteerId;

      if (!shift) {
        rejected.push({ volunteerId: volunteerId, name: name, shiftId: shiftId,
          reason: "Shift '" + shiftId + "' is not in the schedule." });
        return;
      }

      var pairKey = shiftId + "|" + volunteerId;
      if (Object.prototype.hasOwnProperty.call(seenPairs, pairKey)) {
        rejected.push({ volunteerId: volunteerId, name: name, shiftId: shiftId,
          reason: "Duplicate assignment to the same shift." });
        return;
      }
      seenPairs[pairKey] = true;

      if (!vol) {
        rejected.push({ volunteerId: volunteerId, name: volunteerId, shiftId: shiftId,
          reason: "Volunteer '" + volunteerId + "' is not on the cleared roster." });
        return;
      }
      if (!vol.cleared) {
        rejected.push({ volunteerId: volunteerId, name: name, shiftId: shiftId,
          reason: name + " is not cleared and cannot be scheduled." });
        return;
      }

      // Cleared volunteer on a known shift. Count them once toward coverage.
      if (shift.clearedIds.indexOf(volunteerId) === -1) {
        shift.clearedIds.push(volunteerId);
        shift.clearedNames.push(name);
      }
      if (shift.valid) {
        counted.push({
          volunteerId: volunteerId, name: name, shiftId: shiftId,
          date: shift.date, startMin: shift.startMin, endMin: shift.endMin
        });
      }
    });

    // Coverage status per shift.
    shiftResults.forEach(function (sr) {
      sr.clearedCount = sr.clearedIds.length;
      if (!sr.valid) {
        sr.status = "invalid";
        return;
      }
      if (sr.clearedCount < Number(sr.min)) {
        sr.status = "understaffed";
      } else if (sr.clearedCount > Number(sr.max)) {
        sr.status = "overstaffed";
      } else {
        sr.status = "ok";
      }
    });

    // Double-booked volunteers across overlapping valid shifts.
    var conflicts = [];
    var byVolunteer = {};
    counted.forEach(function (c) {
      (byVolunteer[c.volunteerId] = byVolunteer[c.volunteerId] || []).push(c);
    });
    Object.keys(byVolunteer).forEach(function (vid) {
      var items = byVolunteer[vid];
      for (var i = 0; i < items.length; i++) {
        for (var j = i + 1; j < items.length; j++) {
          var a = items[i];
          var b = items[j];
          if (a.date === b.date && overlaps(a.startMin, a.endMin, b.startMin, b.endMin)) {
            conflicts.push({
              volunteerId: vid,
              name: a.name,
              shiftA: a.shiftId,
              shiftB: b.shiftId,
              date: a.date
            });
          }
        }
      }
    });

    var summary = {
      shiftCount: shiftResults.length,
      okCount: shiftResults.filter(function (s) { return s.status === "ok"; }).length,
      understaffed: shiftResults.filter(function (s) { return s.status === "understaffed"; }).length,
      overstaffed: shiftResults.filter(function (s) { return s.status === "overstaffed"; }).length,
      invalid: shiftResults.filter(function (s) { return s.status === "invalid"; }).length,
      conflictCount: conflicts.length,
      rejectedCount: rejected.length
    };

    return { shifts: shiftResults, conflicts: conflicts, rejected: rejected, summary: summary };
  }

  // Parse a cleared roster file. Accepts a bare array of { id, name, cleared }
  // or an object with a "roster" array. Returns { ok, roster } or { ok, error }.
  function parseRosterJson(text) {
    var data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      return { ok: false, error: "File is not valid JSON: " + e.message };
    }
    if (Array.isArray(data)) {
      return { ok: true, roster: data };
    }
    if (data && typeof data === "object" && Array.isArray(data.roster)) {
      return { ok: true, roster: data.roster };
    }
    return { ok: false, error: "File does not contain a roster array." };
  }

  // Parse a schedule file with { shifts, assignments }. Returns
  // { ok, shifts, assignments } or { ok, error }.
  function parseScheduleJson(text) {
    var data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      return { ok: false, error: "File is not valid JSON: " + e.message };
    }
    if (!data || typeof data !== "object" ||
        !Array.isArray(data.shifts) || !Array.isArray(data.assignments)) {
      return { ok: false, error: "File must have a shifts array and an assignments array." };
    }
    return { ok: true, shifts: data.shifts, assignments: data.assignments };
  }

  return {
    toMinutes: toMinutes,
    overlaps: overlaps,
    checkShift: checkShift,
    planCoverage: planCoverage,
    parseRosterJson: parseRosterJson,
    parseScheduleJson: parseScheduleJson
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = CoverageLogic;
}
