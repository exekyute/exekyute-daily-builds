/*
 * Pure logic for the Net Pay Dashboard.
 *
 * No DOM access lives here. Every function takes input and returns a value,
 * so the same code runs in the dashboard and in the tests.html harness.
 *
 * All money is handled as integer cents to avoid floating-point artifacts.
 * Values are only converted back to dollars at display time in formatCad.
 */

// The exact columns the payroll register CSV must contain, in order.
var REGISTER_COLUMNS = [
  "employee_id",
  "name",
  "pay_type",
  "gross_pay",
  "overtime_pay",
  "pretax_deductions",
  "cpp",
  "ei",
  "income_tax",
  "posttax_deductions",
  "total_deductions",
  "net_pay"
];

// Columns the dashboard reads as money (the rest are text labels).
var MONEY_COLUMNS = [
  "gross_pay",
  "overtime_pay",
  "pretax_deductions",
  "cpp",
  "ei",
  "income_tax",
  "posttax_deductions",
  "total_deductions",
  "net_pay"
];

// Parse one CSV line into fields, honouring simple double-quoted values.
function parseCsvLine(line) {
  var fields = [];
  var current = "";
  var inQuotes = false;

  for (var i = 0; i < line.length; i++) {
    var character = line[i];

    if (inQuotes) {
      if (character === '"' && line[i + 1] === '"') {
        current += '"';
        i++;
      } else if (character === '"') {
        inQuotes = false;
      } else {
        current += character;
      }
    } else if (character === '"') {
      inQuotes = true;
    } else if (character === ",") {
      fields.push(current);
      current = "";
    } else {
      current += character;
    }
  }

  fields.push(current);
  return fields.map(function (value) {
    return value.trim();
  });
}

// Split raw CSV text into a header array and an array of row arrays.
// Blank lines are ignored so a trailing newline does not create an empty row.
function parseCsv(text) {
  var lines = text.split(/\r\n|\r|\n/).filter(function (line) {
    return line.trim() !== "";
  });

  if (lines.length === 0) {
    return { header: [], rows: [] };
  }

  var header = parseCsvLine(lines[0]);
  var rows = lines.slice(1).map(parseCsvLine);
  return { header: header, rows: rows };
}

// Return a list of errors describing any missing or unexpected columns.
function validateHeader(header) {
  if (!header || header.length === 0) {
    return ["File has no header row."];
  }

  var errors = [];
  var missing = REGISTER_COLUMNS.filter(function (column) {
    return header.indexOf(column) === -1;
  });
  var extra = header.filter(function (column) {
    return REGISTER_COLUMNS.indexOf(column) === -1;
  });

  if (missing.length > 0) {
    errors.push("Missing column(s): " + missing.join(", "));
  }
  if (extra.length > 0) {
    errors.push("Unexpected column(s): " + extra.join(", "));
  }
  return errors;
}

// Convert a money string such as "1590.00" into integer cents (159000).
// Returns null if the value is not a valid number.
function toCents(value) {
  if (value === null || value === undefined || String(value).trim() === "") {
    return null;
  }
  var amount = Number(value);
  if (isNaN(amount)) {
    return null;
  }
  return Math.round(amount * 100);
}

// Parse the full register text into records, header errors, and row errors.
// A record holds the columns the dashboard renders, with money as cents.
function parseRegister(text) {
  var parsed = parseCsv(text);
  var headerErrors = validateHeader(parsed.header);
  if (headerErrors.length > 0) {
    return { records: [], headerErrors: headerErrors, rowErrors: [] };
  }

  var indexOf = {};
  REGISTER_COLUMNS.forEach(function (column) {
    indexOf[column] = parsed.header.indexOf(column);
  });

  var records = [];
  var rowErrors = [];

  parsed.rows.forEach(function (row, position) {
    var rowNumber = position + 2; // row 1 is the header

    if (row.length !== parsed.header.length) {
      rowErrors.push(
        "Row " + rowNumber + " has " + row.length +
        " fields, expected " + parsed.header.length + "."
      );
      return;
    }

    var cents = {};
    var badField = null;
    MONEY_COLUMNS.forEach(function (column) {
      if (badField) {
        return;
      }
      var converted = toCents(row[indexOf[column]]);
      if (converted === null) {
        badField = column;
      } else {
        cents[column] = converted;
      }
    });

    if (badField) {
      rowErrors.push(
        "Row " + rowNumber + " has a non-numeric value in '" + badField + "'."
      );
      return;
    }

    records.push({
      employeeId: row[indexOf.employee_id],
      name: row[indexOf.name],
      payType: row[indexOf.pay_type],
      grossCents: cents.gross_pay,
      overtimeCents: cents.overtime_pay,
      totalDeductionsCents: cents.total_deductions,
      incomeTaxCents: cents.income_tax,
      netCents: cents.net_pay
    });
  });

  return { records: records, headerErrors: [], rowErrors: rowErrors };
}

// Sum gross and net across all records, in integer cents.
function summarize(records) {
  var totalGrossCents = 0;
  var totalNetCents = 0;
  records.forEach(function (record) {
    totalGrossCents += record.grossCents;
    totalNetCents += record.netCents;
  });
  return { totalGrossCents: totalGrossCents, totalNetCents: totalNetCents };
}

// Format integer cents as Canadian dollars, for example 109401 -> "$1,094.01".
function formatCad(cents) {
  var formatter = new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD"
  });
  return formatter.format(cents / 100);
}

// Make the functions available to tests.html when loaded under Node-free
// browsers, and to a module loader if one is ever used.
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    REGISTER_COLUMNS: REGISTER_COLUMNS,
    MONEY_COLUMNS: MONEY_COLUMNS,
    parseCsvLine: parseCsvLine,
    parseCsv: parseCsv,
    validateHeader: validateHeader,
    toCents: toCents,
    parseRegister: parseRegister,
    summarize: summarize,
    formatCad: formatCad
  };
}
