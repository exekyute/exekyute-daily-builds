/*
 * Pure logic for the Loan Balance Dashboard.
 *
 * Every function here takes plain values and returns plain values. There is no
 * DOM access and no file reading, so the logic can be exercised on its own from
 * tests.html. Money is handled in integer cents, never floating-point dollars,
 * so totals stay exact and free of binary-float artifacts.
 */

var EXPECTED_HEADER = ["period", "payment", "interest", "principal", "balance"];

/*
 * Convert a dollar string like "172.55" into an integer number of cents.
 * Returns null if the value is not a valid non-negative money amount.
 */
function dollarsToCents(raw) {
  if (typeof raw !== "string") {
    return null;
  }
  var text = raw.trim();
  // Optional digits, then an optional two-decimal cents part. No sign allowed.
  if (!/^\d+(\.\d{1,2})?$/.test(text)) {
    return null;
  }
  var parts = text.split(".");
  var whole = parseInt(parts[0], 10);
  var fraction = parts[1] ? parts[1] : "0";
  // Pad "5" to "50" so a single decimal digit reads as tenths of a dollar.
  if (fraction.length === 1) {
    fraction = fraction + "0";
  }
  return whole * 100 + parseInt(fraction, 10);
}

/*
 * Format an integer number of cents as a USD string using Intl.NumberFormat,
 * so amounts always show two decimals and never any floating-point noise.
 */
var usdFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

function formatCents(cents) {
  return usdFormatter.format(cents / 100);
}

/*
 * Split CSV text into trimmed, non-empty lines. Handles both Windows and Unix
 * line endings and ignores a trailing blank line.
 */
function splitLines(text) {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .map(function (line) {
      return line.trim();
    })
    .filter(function (line) {
      return line.length > 0;
    });
}

/*
 * Parse and validate the full schedule CSV.
 *
 * Returns an object:
 *   { ok: true, rows: [...], totals: {...} }            on success
 *   { ok: false, errors: ["...", "..."] }               on failure
 *
 * Every problem found is collected, so the caller can show all of them at once
 * rather than stopping at the first. Each row in rows holds both the integer
 * cent values and pre-formatted display strings.
 */
function parseSchedule(text) {
  var errors = [];

  if (typeof text !== "string" || text.trim().length === 0) {
    return { ok: false, errors: ["The file is empty."] };
  }

  var lines = splitLines(text);
  if (lines.length === 0) {
    return { ok: false, errors: ["The file is empty."] };
  }

  var header = lines[0].split(",").map(function (cell) {
    return cell.trim();
  });
  if (header.join(",") !== EXPECTED_HEADER.join(",")) {
    errors.push(
      "The header must be exactly: " + EXPECTED_HEADER.join(",") + "."
    );
  }

  if (lines.length < 2) {
    errors.push("The file has a header but no schedule rows.");
  }

  var rows = [];
  var totalPaymentCents = 0;
  var totalInterestCents = 0;

  for (var i = 1; i < lines.length; i++) {
    var lineNumber = i + 1; // 1-based, counting the header as line 1
    var cells = lines[i].split(",").map(function (cell) {
      return cell.trim();
    });

    if (cells.length !== EXPECTED_HEADER.length) {
      errors.push(
        "Line " +
          lineNumber +
          " has " +
          cells.length +
          " fields, expected " +
          EXPECTED_HEADER.length +
          "."
      );
      continue;
    }

    var period = cells[0];
    if (!/^\d+$/.test(period) || parseInt(period, 10) < 1) {
      errors.push(
        "Line " + lineNumber + ": period must be a whole number of 1 or more."
      );
    }

    var paymentCents = dollarsToCents(cells[1]);
    var interestCents = dollarsToCents(cells[2]);
    var principalCents = dollarsToCents(cells[3]);
    var balanceCents = dollarsToCents(cells[4]);

    var fieldNames = ["payment", "interest", "principal", "balance"];
    var values = [paymentCents, interestCents, principalCents, balanceCents];
    for (var f = 0; f < values.length; f++) {
      if (values[f] === null) {
        errors.push(
          "Line " +
            lineNumber +
            ": " +
            fieldNames[f] +
            " must be a non-negative dollar amount."
        );
      }
    }

    if (
      paymentCents === null ||
      interestCents === null ||
      principalCents === null ||
      balanceCents === null
    ) {
      continue;
    }

    totalPaymentCents += paymentCents;
    totalInterestCents += interestCents;

    rows.push({
      period: parseInt(period, 10),
      paymentCents: paymentCents,
      interestCents: interestCents,
      principalCents: principalCents,
      balanceCents: balanceCents,
      payment: formatCents(paymentCents),
      interest: formatCents(interestCents),
      principal: formatCents(principalCents),
      balance: formatCents(balanceCents),
    });
  }

  if (errors.length > 0) {
    return { ok: false, errors: errors };
  }

  var finalBalanceCents = rows[rows.length - 1].balanceCents;

  return {
    ok: true,
    rows: rows,
    totals: {
      periods: rows.length,
      totalPaymentCents: totalPaymentCents,
      totalInterestCents: totalInterestCents,
      finalBalanceCents: finalBalanceCents,
      totalPayment: formatCents(totalPaymentCents),
      totalInterest: formatCents(totalInterestCents),
      finalBalance: formatCents(finalBalanceCents),
    },
  };
}

// Export for tests.html (browser global) and any Node-based check.
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    dollarsToCents: dollarsToCents,
    formatCents: formatCents,
    parseSchedule: parseSchedule,
  };
}
