"use strict";

/*
 * Pure logic for the Lease and Rent Roll Dashboard.
 *
 * Every function here takes input and returns a value. Nothing in this file
 * touches the page, reads a file, or knows the DOM exists, which keeps the rules
 * easy to test from tests.html with small CSV strings worked out by hand. The
 * thin wiring in app.js calls these functions and puts the results on the page.
 *
 * Money is handled in integer cents the whole way through and only turned into a
 * string for display with Intl.NumberFormat, so amounts never show a floating
 * point artifact.
 */

var REQUIRED_COLUMNS = [
  "unit",
  "tenant",
  "monthly_rent",
  "prorated_rent",
  "late_fee",
  "amount_due",
  "lease_end"
];

var MONEY_FORMAT = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD"
});

var MS_PER_DAY = 24 * 60 * 60 * 1000;

// Parse a money string such as "$1,250.50" into whole cents (125050). Returns
// null when the value is blank or is not a plain money number.
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

// Format whole cents as a currency string, for example 125050 -> "$1,250.50".
function formatCents(cents) {
  return MONEY_FORMAT.format(cents / 100);
}

// Parse a "YYYY-MM-DD" string into a UTC Date. Returns null when the text is not
// a real calendar date (this also rejects values like 2026-02-30).
function parseDateYMD(text) {
  var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(text).trim());
  if (!match) {
    return null;
  }
  var year = parseInt(match[1], 10);
  var month = parseInt(match[2], 10);
  var day = parseInt(match[3], 10);
  var date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }
  return date;
}

// Whole days from asOf to leaseEnd. Negative when the lease end is in the past.
function daysUntil(asOf, leaseEnd) {
  return Math.round((leaseEnd.getTime() - asOf.getTime()) / MS_PER_DAY);
}

// A lease is flagged when its end is within the window, which includes ends that
// have already passed (a non-positive days value).
function isExpiring(days, windowDays) {
  return days <= windowDays;
}

// Split CSV text into rows of trimmed string fields. Blank lines are dropped.
// The rent roll this dashboard reads uses plain numbers with no embedded commas.
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

// Map each lower-cased column name to its position in the header row.
function headerIndex(header) {
  var index = {};
  for (var i = 0; i < header.length; i++) {
    index[header[i].toLowerCase()] = i;
  }
  return index;
}

// Return the required columns that are not present in the header row.
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

// The main entry point. Takes the raw CSV text, an as-of date string, and a
// window in days, and returns a structured result:
//
//   { ok: false, error: "..." }                          a whole-file problem
//   { ok: true, units: [...], issues: [...], summary }   a usable read
//
// Whole-file problems (empty file, missing column, bad control values) stop the
// read. Row-level problems never stop it: the bad row is left out of units and
// recorded in issues with its line number and reason.
function analyzeRentRoll(csvText, asOfText, windowText) {
  var rows = parseCsv(csvText);
  if (rows.length === 0) {
    return { ok: false, error: "The file is empty." };
  }

  var header = rows[0];
  var missing = missingColumns(header);
  if (missing.length > 0) {
    return { ok: false, error: "Missing required column: " + missing.join(", ") };
  }

  var asOf = parseDateYMD(asOfText);
  if (asOf === null) {
    return { ok: false, error: "The as-of date must be a real YYYY-MM-DD date." };
  }

  var windowDays = parseInt(windowText, 10);
  if (isNaN(windowDays) || windowDays < 0) {
    return { ok: false, error: "The window must be a whole number of days, 0 or more." };
  }

  var index = headerIndex(header);
  var units = [];
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

    var monthly = parseMoneyToCents(row[index.monthly_rent]);
    var prorated = parseMoneyToCents(row[index.prorated_rent]);
    var lateFee = parseMoneyToCents(row[index.late_fee]);
    var amountDue = parseMoneyToCents(row[index.amount_due]);
    if (monthly === null || prorated === null || lateFee === null || amountDue === null) {
      issues.push({ line: line, reason: "a money value is not a number" });
      continue;
    }

    var leaseEnd = parseDateYMD(row[index.lease_end]);
    if (leaseEnd === null) {
      issues.push({ line: line, reason: "lease_end is not a valid YYYY-MM-DD date" });
      continue;
    }

    seen[unit] = true;
    var days = daysUntil(asOf, leaseEnd);
    units.push({
      unit: unit,
      tenant: tenant,
      monthlyCents: monthly,
      proratedCents: prorated,
      lateFeeCents: lateFee,
      amountDueCents: amountDue,
      leaseEnd: row[index.lease_end],
      daysUntil: days,
      expiring: isExpiring(days, windowDays)
    });
  }

  var totalBilled = 0;
  var flagged = 0;
  for (var j = 0; j < units.length; j++) {
    totalBilled += units[j].amountDueCents;
    if (units[j].expiring) {
      flagged += 1;
    }
  }

  return {
    ok: true,
    units: units,
    issues: issues,
    summary: {
      count: units.length,
      totalBilledCents: totalBilled,
      flaggedCount: flagged,
      windowDays: windowDays
    }
  };
}
