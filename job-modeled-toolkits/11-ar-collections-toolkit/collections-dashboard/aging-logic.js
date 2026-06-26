/*
 * Pure logic for the Collections Aging Dashboard.
 *
 * Every function here takes plain values and returns plain values. There is no
 * DOM access and no file access, so these functions can be tested on their own
 * in tests.html. The DOM wiring lives in dashboard.js.
 *
 * Money is handled as integer cents to avoid floating-point artifacts, and
 * formatted for display with Intl.NumberFormat.
 */

// The exact columns the aging report from the Python engine must have.
var EXPECTED_HEADER = [
  "invoice_number",
  "customer",
  "issue_date",
  "due_date",
  "amount",
  "days_past_due",
  "aging_bucket",
  "late_fee",
  "total_due",
];

// Aging buckets in display order, matching the Python engine.
var BUCKETS = ["Current", "1-30", "31-60", "61-90", "90-plus"];

var MONEY_FORMAT = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

// Convert a "1015.00" style money string into integer cents, or null if the
// value is blank or not a number.
function dollarsToCents(text) {
  if (text === undefined || text === null || String(text).trim() === "") {
    return null;
  }
  var value = Number(text);
  if (Number.isNaN(value)) {
    return null;
  }
  return Math.round(value * 100);
}

// Format integer cents as a US dollar string, e.g. 101500 -> "$1,015.00".
function formatMoney(cents) {
  return MONEY_FORMAT.format(cents / 100);
}

// Map an aging bucket to its CSS class for color coding.
function bucketClass(bucket) {
  var map = {
    "Current": "b-current",
    "1-30": "b-1-30",
    "31-60": "b-31-60",
    "61-90": "b-61-90",
    "90-plus": "b-90-plus",
  };
  return map[bucket] || "";
}

// Parse aging report CSV text into rows.
//
// Returns { rows, skipped, error }:
//   rows    - array of parsed invoice objects (integer cents for money)
//   skipped - count of data rows skipped because they were malformed
//   error   - a message when the file is empty or the header is wrong, else null
function parseAgingCsv(text) {
  var lines = String(text)
    .split(/\r?\n/)
    .filter(function (line) {
      return line.trim() !== "";
    });

  if (lines.length === 0) {
    return { rows: [], skipped: 0, error: "The file is empty." };
  }

  var header = lines[0].split(",").map(function (field) {
    return field.trim();
  });

  var headerMatches =
    header.length === EXPECTED_HEADER.length &&
    EXPECTED_HEADER.every(function (name, index) {
      return name === header[index];
    });

  if (!headerMatches) {
    return {
      rows: [],
      skipped: 0,
      error:
        "Unexpected columns. Load an aging report produced by the AR Aging and Late-Fee Engine.",
    };
  }

  var rows = [];
  var skipped = 0;

  for (var i = 1; i < lines.length; i++) {
    var fields = lines[i].split(",");
    if (fields.length !== EXPECTED_HEADER.length) {
      skipped++;
      continue;
    }

    var amountCents = dollarsToCents(fields[4]);
    var daysPastDue = parseInt(fields[5], 10);
    var bucket = fields[6].trim();
    var lateFeeCents = dollarsToCents(fields[7]);
    var totalDueCents = dollarsToCents(fields[8]);

    var malformed =
      amountCents === null ||
      lateFeeCents === null ||
      totalDueCents === null ||
      Number.isNaN(daysPastDue) ||
      BUCKETS.indexOf(bucket) === -1;

    if (malformed) {
      skipped++;
      continue;
    }

    rows.push({
      invoiceNumber: fields[0].trim(),
      customer: fields[1].trim(),
      issueDate: fields[2].trim(),
      dueDate: fields[3].trim(),
      amountCents: amountCents,
      daysPastDue: daysPastDue,
      bucket: bucket,
      lateFeeCents: lateFeeCents,
      totalDueCents: totalDueCents,
    });
  }

  return { rows: rows, skipped: skipped, error: null };
}

// Count and total outstanding (sum of total due) per bucket.
// Always includes every bucket in BUCKETS, even when the count is zero.
function bucketTotals(rows) {
  var totals = {};
  BUCKETS.forEach(function (bucket) {
    totals[bucket] = { count: 0, totalCents: 0 };
  });
  rows.forEach(function (row) {
    totals[row.bucket].count += 1;
    totals[row.bucket].totalCents += row.totalDueCents;
  });
  return totals;
}

// Sum of total due across every row, in integer cents.
function grandTotalCents(rows) {
  return rows.reduce(function (sum, row) {
    return sum + row.totalDueCents;
  }, 0);
}

// Make the functions available to tests.html when loaded as a module too.
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    EXPECTED_HEADER: EXPECTED_HEADER,
    BUCKETS: BUCKETS,
    dollarsToCents: dollarsToCents,
    formatMoney: formatMoney,
    bucketClass: bucketClass,
    parseAgingCsv: parseAgingCsv,
    bucketTotals: bucketTotals,
    grandTotalCents: grandTotalCents,
  };
}
