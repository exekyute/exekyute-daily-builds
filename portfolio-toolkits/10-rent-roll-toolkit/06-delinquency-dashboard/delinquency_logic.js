"use strict";

/*
 * Pure logic for the Delinquency Dashboard.
 *
 * Every function here takes input and returns a value. Nothing in this file
 * touches the page or reads a file, so the rules can be tested from tests.html
 * with small CSV strings. The thin wiring in app.js calls these functions and
 * renders the result.
 *
 * Money is handled in integer cents and only formatted for display with
 * Intl.NumberFormat. The aging buckets have a fixed order from least to most
 * overdue, which drives both the totals strip and the worst-first table sort.
 */

var REQUIRED_COLUMNS = [
  "unit",
  "tenant",
  "charge_type",
  "due_date",
  "balance",
  "days_overdue",
  "bucket",
  "late_fee",
  "total_owed"
];

// Buckets from least to most overdue. The index doubles as a severity rank.
var BUCKET_ORDER = ["current", "1-30", "31-60", "61-90", "90+"];

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

function parseIntStrict(text) {
  var cleaned = String(text).trim();
  if (!/^-?\d+$/.test(cleaned)) {
    return null;
  }
  return parseInt(cleaned, 10);
}

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

// The severity rank of a bucket, used to sort the worst overdue first. An unknown
// bucket sorts last.
function bucketRank(bucket) {
  var rank = BUCKET_ORDER.indexOf(bucket);
  return rank === -1 ? -1 : rank;
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

// Read the aging CSV into a structured result. Whole-file problems (empty, missing
// column) stop the read; row-level problems are collected as issues while the good
// rows still come through.
function analyzeAging(csvText) {
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

    var balanceCents = parseMoneyToCents(row[index.balance]);
    var lateFeeCents = parseMoneyToCents(row[index.late_fee]);
    var owedCents = parseMoneyToCents(row[index.total_owed]);
    if (balanceCents === null || lateFeeCents === null || owedCents === null) {
      issues.push({ line: line, reason: "a money value is not a number" });
      continue;
    }

    var days = parseIntStrict(row[index.days_overdue]);
    if (days === null) {
      issues.push({ line: line, reason: "days_overdue is not a whole number" });
      continue;
    }

    if (!isValidDate(row[index.due_date])) {
      issues.push({ line: line, reason: "due_date is not a valid YYYY-MM-DD date" });
      continue;
    }

    var bucket = row[index.bucket];
    if (bucketRank(bucket) === -1) {
      issues.push({ line: line, reason: "unknown bucket '" + bucket + "'" });
      continue;
    }

    seen[unit] = true;
    records.push({
      unit: unit,
      tenant: tenant,
      chargeType: row[index.charge_type],
      dueDate: row[index.due_date],
      balanceCents: balanceCents,
      daysOverdue: days,
      bucket: bucket,
      lateFeeCents: lateFeeCents,
      owedCents: owedCents
    });
  }

  return {
    ok: true,
    rows: records,
    issues: issues,
    summary: summarize(records)
  };
}

// Build overall and per-bucket totals. Buckets are keyed in fixed aging order so
// the strip always shows current through 90+ even when a bucket is empty.
function summarize(records) {
  var buckets = {};
  for (var b = 0; b < BUCKET_ORDER.length; b++) {
    buckets[BUCKET_ORDER[b]] = {
      count: 0,
      balanceCents: 0,
      lateFeeCents: 0,
      owedCents: 0
    };
  }
  var totalBalance = 0;
  var totalLateFee = 0;
  var totalOwed = 0;
  for (var i = 0; i < records.length; i++) {
    var r = records[i];
    var slot = buckets[r.bucket];
    slot.count += 1;
    slot.balanceCents += r.balanceCents;
    slot.lateFeeCents += r.lateFeeCents;
    slot.owedCents += r.owedCents;
    totalBalance += r.balanceCents;
    totalLateFee += r.lateFeeCents;
    totalOwed += r.owedCents;
  }
  return {
    count: records.length,
    totalBalanceCents: totalBalance,
    totalLateFeeCents: totalLateFee,
    totalOwedCents: totalOwed,
    buckets: buckets
  };
}

// Sort the most overdue bucket first, and within a bucket the largest amount owed
// first. Returns a new array and does not change the input.
function sortWorstFirst(records) {
  var copy = records.slice();
  copy.sort(function (a, b) {
    var ra = bucketRank(a.bucket);
    var rb = bucketRank(b.bucket);
    if (ra !== rb) {
      return rb - ra;
    }
    return b.owedCents - a.owedCents;
  });
  return copy;
}
