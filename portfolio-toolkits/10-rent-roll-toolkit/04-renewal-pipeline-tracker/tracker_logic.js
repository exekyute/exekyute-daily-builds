"use strict";

/*
 * Pure logic for the Renewal Pipeline Tracker.
 *
 * Every function here takes input and returns a value. Nothing in this file
 * touches the page or reads a file, so the rules can be tested from tests.html
 * with small CSV strings. The thin wiring in app.js calls these functions and
 * renders the result.
 *
 * Money is handled in integer cents and only formatted for display with
 * Intl.NumberFormat. Dates arrive as "YYYY-MM-DD" strings, which sort correctly
 * as plain text, so the table can sort by a date column without parsing it into a
 * Date object.
 */

var REQUIRED_COLUMNS = [
  "unit",
  "tenant",
  "current_rent",
  "lease_end",
  "renewal_start",
  "renewal_end",
  "escalated_rent",
  "notice_due_date",
  "days_to_notice",
  "status"
];

// The order statuses are reported and sorted in. Lower number is more urgent.
var STATUS_PRIORITY = { due_now: 0, upcoming: 1, expired: 2 };
var STATUS_ORDER = ["due_now", "upcoming", "expired"];

var MONEY_FORMAT = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD"
});

function parseMoneyToCents(text) {
  var cleaned = String(text).replace(/[$,\s]/g, "");
  if (cleaned === "") {
    return null;
  }
  if (!/^-?\d+(\.\d{1,2})?$/.test(cleaned)) {
    return null;
  }
  var negative = cleaned.charAt(0) === "-";
  if (negative) {
    cleaned = cleaned.slice(1);
  }
  var parts = cleaned.split(".");
  var cents = parts.length > 1 ? parts[1] : "";
  while (cents.length < 2) {
    cents += "0";
  }
  var total = parseInt(parts[0], 10) * 100 + parseInt(cents, 10);
  return negative ? -total : total;
}

function formatCents(cents) {
  return MONEY_FORMAT.format(cents / 100);
}

// Parse a strict whole number, allowing a leading minus. Returns null otherwise.
function parseIntStrict(text) {
  var cleaned = String(text).trim();
  if (!/^-?\d+$/.test(cleaned)) {
    return null;
  }
  return parseInt(cleaned, 10);
}

// Validate a "YYYY-MM-DD" string is a real calendar date. Returns true or false.
function isValidDate(text) {
  var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(text).trim());
  if (!match) {
    return false;
  }
  var year = parseInt(match[1], 10);
  var month = parseInt(match[2], 10);
  var day = parseInt(match[3], 10);
  var date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  );
}

function parseCsv(text) {
  var lines = String(text).split(/\r?\n/);
  var rows = [];
  for (var i = 0; i < lines.length; i++) {
    if (lines[i].trim() === "") {
      continue;
    }
    rows.push(
      lines[i].split(",").map(function (field) {
        return field.trim();
      })
    );
  }
  return rows;
}

function headerIndex(header) {
  var index = {};
  for (var i = 0; i < header.length; i++) {
    index[header[i].toLowerCase()] = i;
  }
  return index;
}

function missingColumns(header) {
  var present = headerIndex(header);
  var missing = [];
  for (var i = 0; i < REQUIRED_COLUMNS.length; i++) {
    if (!(REQUIRED_COLUMNS[i] in present)) {
      missing.push(REQUIRED_COLUMNS[i]);
    }
  }
  return missing;
}

// Read the renewals CSV into a structured result. Whole-file problems (empty,
// missing column) stop the read; row-level problems are collected as issues while
// the good rows still come through.
function analyzeRenewals(csvText) {
  var rows = parseCsv(csvText);
  if (rows.length === 0) {
    return { ok: false, error: "The file is empty." };
  }

  var header = rows[0];
  var missing = missingColumns(header);
  if (missing.length > 0) {
    return { ok: false, error: "Missing required column: " + missing.join(", ") };
  }

  var index = headerIndex(header);
  var records = [];
  var issues = [];
  var seen = {};

  for (var i = 1; i < rows.length; i++) {
    var row = rows[i];
    var line = i + 1;

    if (row.length !== header.length) {
      issues.push({
        line: line,
        reason: "expected " + header.length + " fields, found " + row.length
      });
      continue;
    }

    var unit = row[index.unit];
    var tenant = row[index.tenant];
    if (unit === "") {
      issues.push({ line: line, reason: "unit is blank" });
      continue;
    }
    if (seen[unit]) {
      issues.push({ line: line, reason: "duplicate unit '" + unit + "'" });
      continue;
    }
    if (tenant === "") {
      issues.push({ line: line, reason: "tenant is blank" });
      continue;
    }

    var currentCents = parseMoneyToCents(row[index.current_rent]);
    var escalatedCents = parseMoneyToCents(row[index.escalated_rent]);
    if (currentCents === null || escalatedCents === null) {
      issues.push({ line: line, reason: "a rent value is not a number" });
      continue;
    }

    var days = parseIntStrict(row[index.days_to_notice]);
    if (days === null) {
      issues.push({ line: line, reason: "days_to_notice is not a whole number" });
      continue;
    }

    var leaseEnd = row[index.lease_end];
    var renewalStart = row[index.renewal_start];
    var renewalEnd = row[index.renewal_end];
    var noticeDue = row[index.notice_due_date];
    if (
      !isValidDate(leaseEnd) ||
      !isValidDate(renewalStart) ||
      !isValidDate(renewalEnd) ||
      !isValidDate(noticeDue)
    ) {
      issues.push({ line: line, reason: "a date is not a valid YYYY-MM-DD date" });
      continue;
    }

    var status = row[index.status];
    if (status === "") {
      issues.push({ line: line, reason: "status is blank" });
      continue;
    }

    seen[unit] = true;
    records.push({
      unit: unit,
      tenant: tenant,
      currentCents: currentCents,
      escalatedCents: escalatedCents,
      leaseEnd: leaseEnd,
      renewalStart: renewalStart,
      renewalEnd: renewalEnd,
      noticeDue: noticeDue,
      daysToNotice: days,
      status: status
    });
  }

  var counts = { due_now: 0, upcoming: 0, expired: 0, other: 0 };
  for (var j = 0; j < records.length; j++) {
    var key = records[j].status;
    if (key in counts) {
      counts[key] += 1;
    } else {
      counts.other += 1;
    }
  }

  return {
    ok: true,
    rows: records,
    issues: issues,
    summary: { count: records.length, counts: counts }
  };
}

// The value a given column sorts on. Money sorts by cents, days by number, and
// everything else as text (dates included, since YYYY-MM-DD sorts chronologically).
function sortValue(record, key) {
  if (key === "current_rent") {
    return record.currentCents;
  }
  if (key === "escalated_rent") {
    return record.escalatedCents;
  }
  if (key === "days_to_notice") {
    return record.daysToNotice;
  }
  if (key === "lease_end") {
    return record.leaseEnd;
  }
  if (key === "notice_due_date") {
    return record.noticeDue;
  }
  if (key === "status") {
    return record.status;
  }
  if (key === "tenant") {
    return record.tenant;
  }
  return record.unit;
}

// The default order: most urgent status first, then soonest notice within a status.
function defaultCompare(a, b) {
  var pa = a.status in STATUS_PRIORITY ? STATUS_PRIORITY[a.status] : 99;
  var pb = b.status in STATUS_PRIORITY ? STATUS_PRIORITY[b.status] : 99;
  if (pa !== pb) {
    return pa - pb;
  }
  return a.daysToNotice - b.daysToNotice;
}

// Return a new array sorted by the given key and direction. The key "default"
// uses the urgency order above. Array.prototype.sort is stable, so ties keep
// their existing order.
function sortRows(rows, key, direction) {
  var copy = rows.slice();
  if (key === "default") {
    copy.sort(defaultCompare);
    return copy;
  }
  var dir = direction === "desc" ? -1 : 1;
  copy.sort(function (a, b) {
    var av = sortValue(a, key);
    var bv = sortValue(b, key);
    if (av < bv) {
      return -1 * dir;
    }
    if (av > bv) {
      return 1 * dir;
    }
    return 0;
  });
  return copy;
}
