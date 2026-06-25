/*
 * hours_logic.js
 *
 * Pure business logic for the Volunteer Hours Dashboard. No DOM access and no
 * browser APIs, so every rule can be exercised directly from tests.html. The
 * page script (app.js) reads the CSV text with the FileReader API and passes it
 * here.
 *
 * Durations are tracked in whole minutes from the start and end times, so totals
 * never drift the way fractional hours can. Hours are only formatted at the end
 * for display. Dates are YYYY-MM-DD and times are 24-hour HH:MM. An entry does
 * not cross midnight. Overlap uses half-open ranges, so two entries that only
 * touch do not overlap.
 */
var HoursLogic = (function () {
  "use strict";

  var DEFAULT_CONFIG = {
    milestone_hours: [10, 25, 50, 100],
    max_entry_minutes: 720,   // 12 hours in a single entry
    max_daily_minutes: 840    // 14 hours logged by one volunteer in one day
  };

  var EXPECTED_COLUMNS = ["entry_id", "volunteer_id", "volunteer_name", "date", "start_time", "end_time"];

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

  function isYmd(value) {
    if (typeof value !== "string") {
      return false;
    }
    var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
    if (!match) {
      return false;
    }
    var year = Number(match[1]);
    var month = Number(match[2]);
    var day = Number(match[3]);
    if (month < 1 || month > 12 || day < 1 || day > 31) {
      return false;
    }
    var date = new Date(Date.UTC(year, month - 1, day));
    return date.getUTCFullYear() === year &&
      date.getUTCMonth() === month - 1 &&
      date.getUTCDate() === day;
  }

  function overlaps(aStart, aEnd, bStart, bEnd) {
    return aStart < bEnd && bStart < aEnd;
  }

  // Whole minutes as H:MM, for example 90 -> "1:30", 600 -> "10:00".
  function formatHM(minutes) {
    var h = Math.floor(minutes / 60);
    var m = minutes % 60;
    return h + ":" + (m < 10 ? "0" + m : String(m));
  }

  // Split a single CSV line into fields. The sample data has no quoted commas,
  // so a plain split is enough and stays easy to read.
  function splitLine(line) {
    return line.split(",").map(function (f) { return f.trim(); });
  }

  // Parse CSV text into valid rows and rejected rows. Returns:
  //   { rows: [ ...valid ], rejected: [ { line, raw, reason } ], headerError }
  // A valid row is { entry_id, volunteer_id, volunteer_name, date, start, end,
  // startMin, endMin, minutes }.
  function parseCsv(text) {
    var rows = [];
    var rejected = [];
    var lines = String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");

    // Drop a trailing blank line if present.
    while (lines.length && lines[lines.length - 1].trim() === "") {
      lines.pop();
    }
    if (lines.length === 0) {
      return { rows: rows, rejected: rejected, headerError: "The file is empty." };
    }

    var header = splitLine(lines[0]).map(function (h) { return h.toLowerCase(); });
    var headerError = "";
    if (header.length !== EXPECTED_COLUMNS.length ||
        EXPECTED_COLUMNS.some(function (col, i) { return header[i] !== col; })) {
      headerError = "Header should be: " + EXPECTED_COLUMNS.join(", ") + ".";
    }

    var seenIds = {};
    for (var i = 1; i < lines.length; i++) {
      var raw = lines[i];
      if (raw.trim() === "") {
        continue;
      }
      var lineNumber = i + 1;
      var fields = splitLine(raw);

      if (fields.length !== EXPECTED_COLUMNS.length) {
        rejected.push({ line: lineNumber, raw: raw,
          reason: "Row has " + fields.length + " fields, expected " + EXPECTED_COLUMNS.length + "." });
        continue;
      }

      var row = {
        entry_id: fields[0],
        volunteer_id: fields[1],
        volunteer_name: fields[2],
        date: fields[3],
        start: fields[4],
        end: fields[5]
      };

      var blank = EXPECTED_COLUMNS.filter(function (col, idx) { return fields[idx] === ""; });
      if (blank.length) {
        rejected.push({ line: lineNumber, raw: raw,
          reason: "Blank required field: " + blank.join(", ") + "." });
        continue;
      }

      var idKey = row.entry_id.toLowerCase();
      if (Object.prototype.hasOwnProperty.call(seenIds, idKey)) {
        rejected.push({ line: lineNumber, raw: raw,
          reason: "Duplicate entry id '" + row.entry_id + "'." });
        continue;
      }

      if (!isYmd(row.date)) {
        rejected.push({ line: lineNumber, raw: raw,
          reason: "Date '" + row.date + "' is not a real YYYY-MM-DD date." });
        continue;
      }

      var startMin = toMinutes(row.start);
      var endMin = toMinutes(row.end);
      if (startMin === null || endMin === null) {
        rejected.push({ line: lineNumber, raw: raw,
          reason: "Start or end time is not a real 24-hour HH:MM time." });
        continue;
      }
      if (endMin <= startMin) {
        rejected.push({ line: lineNumber, raw: raw,
          reason: "End time is not after start time." });
        continue;
      }

      seenIds[idKey] = true;
      row.startMin = startMin;
      row.endMin = endMin;
      row.minutes = endMin - startMin;
      rows.push(row);
    }

    return { rows: rows, rejected: rejected, headerError: headerError };
  }

  function fillConfig(config) {
    var c = config || {};
    return {
      milestone_hours: Array.isArray(c.milestone_hours) ? c.milestone_hours.slice() : DEFAULT_CONFIG.milestone_hours.slice(),
      max_entry_minutes: c.max_entry_minutes === undefined || c.max_entry_minutes === null || c.max_entry_minutes === ""
        ? DEFAULT_CONFIG.max_entry_minutes : Number(c.max_entry_minutes),
      max_daily_minutes: c.max_daily_minutes === undefined || c.max_daily_minutes === null || c.max_daily_minutes === ""
        ? DEFAULT_CONFIG.max_daily_minutes : Number(c.max_daily_minutes)
    };
  }

  function highestMilestone(totalMinutes, milestoneHours) {
    var best = null;
    milestoneHours.slice().sort(function (a, b) { return a - b; }).forEach(function (h) {
      if (totalMinutes >= h * 60) {
        best = h;
      }
    });
    return best;
  }

  // Summarize valid rows. Returns:
  //   { totals: [ { volunteer_id, name, entries, minutes, formatted, milestone } ],
  //     milestones: [ { volunteer_id, name, hours } ],
  //     anomalies: [ { type, volunteer_id, name, detail } ] }
  function summarize(rows, config) {
    var c = fillConfig(config);
    var byVolunteer = {};
    var order = [];

    rows.forEach(function (row) {
      var key = row.volunteer_id;
      if (!Object.prototype.hasOwnProperty.call(byVolunteer, key)) {
        byVolunteer[key] = { volunteer_id: key, name: row.volunteer_name, entries: [], minutes: 0 };
        order.push(key);
      }
      var v = byVolunteer[key];
      v.entries.push(row);
      v.minutes += row.minutes;
      if (!v.name && row.volunteer_name) {
        v.name = row.volunteer_name;
      }
    });

    var totals = order.map(function (key) {
      var v = byVolunteer[key];
      return {
        volunteer_id: v.volunteer_id,
        name: v.name,
        entries: v.entries.length,
        minutes: v.minutes,
        formatted: formatHM(v.minutes),
        milestone: highestMilestone(v.minutes, c.milestone_hours)
      };
    }).sort(function (a, b) {
      return b.minutes - a.minutes || a.name.localeCompare(b.name);
    });

    var milestones = totals
      .filter(function (t) { return t.milestone !== null; })
      .map(function (t) { return { volunteer_id: t.volunteer_id, name: t.name, hours: t.milestone }; });

    var anomalies = [];

    order.forEach(function (key) {
      var v = byVolunteer[key];

      // Excessive single entries.
      v.entries.forEach(function (row) {
        if (row.minutes > c.max_entry_minutes) {
          anomalies.push({
            type: "excessive-entry",
            volunteer_id: v.volunteer_id,
            name: v.name,
            detail: "Entry " + row.entry_id + " on " + row.date + " runs " + formatHM(row.minutes) +
              ", over the " + formatHM(c.max_entry_minutes) + " single-entry limit."
          });
        }
      });

      // Group the volunteer's entries by date for overlap and daily totals.
      var byDate = {};
      v.entries.forEach(function (row) {
        (byDate[row.date] = byDate[row.date] || []).push(row);
      });

      Object.keys(byDate).forEach(function (date) {
        var dayEntries = byDate[date];

        // Overlapping entries on the same date.
        for (var i = 0; i < dayEntries.length; i++) {
          for (var j = i + 1; j < dayEntries.length; j++) {
            var a = dayEntries[i];
            var b = dayEntries[j];
            if (overlaps(a.startMin, a.endMin, b.startMin, b.endMin)) {
              anomalies.push({
                type: "overlap",
                volunteer_id: v.volunteer_id,
                name: v.name,
                detail: "Entries " + a.entry_id + " and " + b.entry_id + " on " + date + " overlap in time."
              });
            }
          }
        }

        // Excessive daily total.
        var dayMinutes = dayEntries.reduce(function (sum, row) { return sum + row.minutes; }, 0);
        if (dayMinutes > c.max_daily_minutes) {
          anomalies.push({
            type: "excessive-daily",
            volunteer_id: v.volunteer_id,
            name: v.name,
            detail: "Logged " + formatHM(dayMinutes) + " on " + date +
              ", over the " + formatHM(c.max_daily_minutes) + " daily limit."
          });
        }
      });
    });

    return { totals: totals, milestones: milestones, anomalies: anomalies };
  }

  return {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    EXPECTED_COLUMNS: EXPECTED_COLUMNS,
    toMinutes: toMinutes,
    isYmd: isYmd,
    overlaps: overlaps,
    formatHM: formatHM,
    parseCsv: parseCsv,
    summarize: summarize
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HoursLogic;
}
