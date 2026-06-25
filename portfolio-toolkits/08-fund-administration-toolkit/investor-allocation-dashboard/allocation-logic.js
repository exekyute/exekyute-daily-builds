/*
 * Pure logic for the Investor Allocation Dashboard.
 *
 * None of these functions touch the page. They take plain text or numbers and
 * return plain values, so they can be tested on their own in tests.html.
 *
 * Money is handled in whole cents (integers). Dollar strings are converted to
 * cents on the way in and formatted back to dollars only for display, so the
 * arithmetic never shows floating-point artifacts.
 */

var EXPECTED_HEADER = ["investor", "commitment", "ownership_pct", "called_amount"];

var dollarsFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

function parseDollarsToCents(text) {
  var cleaned = String(text).trim().replace(/,/g, "");
  if (cleaned === "" || !/^-?\d+(\.\d+)?$/.test(cleaned)) {
    throw new Error('"' + text + '" is not a valid dollar amount.');
  }
  var negative = cleaned.charAt(0) === "-";
  var digits = negative ? cleaned.slice(1) : cleaned;
  var parts = digits.split(".");
  var whole = parts[0];
  var fraction = (parts[1] || "") + "00";
  var cents = Number(whole) * 100 + Number(fraction.slice(0, 2));
  return negative ? -cents : cents;
}

function parseCsv(text) {
  var normalised = String(text).replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  if (normalised === "") {
    throw new Error("The file is empty.");
  }
  var lines = normalised.split("\n");
  var header = lines[0].split(",").map(function (field) {
    return field.trim();
  });
  var rows = lines.slice(1).map(function (line) {
    return line.split(",").map(function (field) {
      return field.trim();
    });
  });
  return { header: header, rows: rows };
}

function buildAllocationRows(parsed) {
  var header = parsed.header.map(function (field) {
    return field.toLowerCase();
  });
  var headerMatches =
    header.length === EXPECTED_HEADER.length &&
    EXPECTED_HEADER.every(function (name, index) {
      return header[index] === name;
    });
  if (!headerMatches) {
    throw new Error(
      "Header must be investor,commitment,ownership_pct,called_amount."
    );
  }
  if (parsed.rows.length === 0) {
    throw new Error("The allocation file has no investor rows.");
  }

  return parsed.rows.map(function (fields, index) {
    var lineNumber = index + 2;
    if (fields.length !== EXPECTED_HEADER.length) {
      throw new Error(
        "Line " +
          lineNumber +
          ": expected " +
          EXPECTED_HEADER.length +
          " fields but found " +
          fields.length +
          "."
      );
    }
    var investor = fields[0];
    if (investor === "") {
      throw new Error("Line " + lineNumber + ": investor name is blank.");
    }
    return {
      investor: investor,
      commitmentCents: parseDollarsToCents(fields[1]),
      calledCents: parseDollarsToCents(fields[3]),
    };
  });
}

function computeRemainingCents(commitmentCents, calledCents) {
  return commitmentCents - calledCents;
}

function computeOwnershipPct(commitmentCents, totalCommitmentCents) {
  if (totalCommitmentCents === 0) {
    return 0;
  }
  return (commitmentCents / totalCommitmentCents) * 100;
}

function summarize(rows) {
  var totalCommitment = 0;
  var totalCalled = 0;
  var totalRemaining = 0;
  rows.forEach(function (row) {
    totalCommitment += row.commitmentCents;
    totalCalled += row.calledCents;
    totalRemaining += computeRemainingCents(row.commitmentCents, row.calledCents);
  });
  return {
    totalCommitment: totalCommitment,
    totalCalled: totalCalled,
    totalRemaining: totalRemaining,
    investorCount: rows.length,
  };
}

function centsToDisplay(cents) {
  return dollarsFormatter.format(cents / 100);
}

function formatPercent(value) {
  return value.toFixed(4) + "%";
}

// Allow Node to import these for a quick command-line sanity check. Browsers
// ignore this block because there is no `module` object on the page.
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    parseDollarsToCents: parseDollarsToCents,
    parseCsv: parseCsv,
    buildAllocationRows: buildAllocationRows,
    computeRemainingCents: computeRemainingCents,
    computeOwnershipPct: computeOwnershipPct,
    summarize: summarize,
    centsToDisplay: centsToDisplay,
    formatPercent: formatPercent,
  };
}
