/*
 * Pure logic for the Shipment Landed-Cost Dashboard.
 *
 * Every function here takes input and returns a value. There is no DOM access,
 * no file reading, and no rendering, so the functions can be exercised directly
 * by tests.html. The DOM wiring lives in app.js.
 *
 * All money is handled as integer cents. Dollar strings from the CSV are parsed
 * straight into cents without floating-point arithmetic, totals are summed in
 * cents, and amounts are formatted for display once with Intl.NumberFormat. This
 * keeps floating-point artifacts off the screen entirely.
 */
(function (global) {
  "use strict";

  var REQUIRED_COLUMNS = [
    "line_id",
    "description",
    "quantity",
    "unit_cost",
    "allocated_freight",
    "landed_unit_cost",
  ];

  var moneyFormatter = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  });

  /*
   * Parse CSV text into a header row and data records. Handles quoted fields
   * that contain commas or escaped quotes. Returns:
   *   { header: [string], records: [{ line: number, values: {col: string} }] }
   * line is the 1-based line in the source text (the header is line 1).
   */
  function parseCsv(text) {
    var rows = parseRows(text);
    if (rows.length === 0) {
      return { header: [], records: [] };
    }
    var header = rows[0].cells;
    var records = [];
    for (var i = 1; i < rows.length; i++) {
      var cells = rows[i].cells;
      // Skip a fully blank trailing line.
      if (cells.length === 1 && cells[0] === "") {
        continue;
      }
      var values = {};
      for (var c = 0; c < header.length; c++) {
        values[header[c]] = c < cells.length ? cells[c] : "";
      }
      records.push({ line: rows[i].line, values: values, fieldCount: cells.length });
    }
    return { header: header, records: records };
  }

  // Split raw text into rows of cells, tracking the source line number.
  function parseRows(text) {
    var normalized = String(text).replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    var rows = [];
    var cells = [];
    var field = "";
    var inQuotes = false;
    var line = 1;
    var startedRow = false;

    for (var i = 0; i < normalized.length; i++) {
      var ch = normalized[i];
      startedRow = true;
      if (inQuotes) {
        if (ch === '"') {
          if (normalized[i + 1] === '"') {
            field += '"';
            i++;
          } else {
            inQuotes = false;
          }
        } else {
          field += ch;
        }
      } else if (ch === '"') {
        inQuotes = true;
      } else if (ch === ",") {
        cells.push(field);
        field = "";
      } else if (ch === "\n") {
        cells.push(field);
        rows.push({ cells: cells, line: line });
        cells = [];
        field = "";
        line++;
        startedRow = false;
      } else {
        field += ch;
      }
    }
    if (startedRow || field !== "" || cells.length > 0) {
      cells.push(field);
      rows.push({ cells: cells, line: line });
    }
    return rows;
  }

  // Return the required columns absent from a header, in order.
  function missingColumns(header) {
    var present = {};
    (header || []).forEach(function (name) {
      present[name] = true;
    });
    return REQUIRED_COLUMNS.filter(function (name) {
      return !present[name];
    });
  }

  /*
   * Parse a money string such as "25.93" into integer cents (2593). Rejects
   * blanks and anything that is not a plain decimal with up to two places.
   * Throws Error with a short reason so the caller can attach a line number.
   */
  function toCents(raw) {
    if (raw === null || raw === undefined) {
      throw new Error("missing value");
    }
    var text = String(raw).trim();
    if (text === "") {
      throw new Error("missing value");
    }
    var match = text.match(/^(-)?(\d+)(?:\.(\d{1,2}))?$/);
    if (!match) {
      throw new Error("not a valid amount");
    }
    var sign = match[1] ? -1 : 1;
    var whole = parseInt(match[2], 10);
    var fraction = match[3] ? (match[3].length === 1 ? match[3] + "0" : match[3]) : "00";
    return sign * (whole * 100 + parseInt(fraction, 10));
  }

  // Parse a positive integer quantity. Throws on blanks, non-integers, and
  // values that are zero or negative.
  function parseQuantity(raw) {
    if (raw === null || raw === undefined || String(raw).trim() === "") {
      throw new Error("missing value");
    }
    var text = String(raw).trim();
    if (!/^\d+$/.test(text)) {
      throw new Error("not a whole number");
    }
    var value = parseInt(text, 10);
    if (value <= 0) {
      throw new Error("must be greater than 0");
    }
    return value;
  }

  /*
   * Build display rows from parsed records. Each row carries the raw values plus
   * money in cents and the derived goods value and line landed cost. Bad rows
   * are collected as errors (with their line number) rather than dropped, so the
   * caller can show every problem.
   * Returns { rows: [...], errors: [string] }.
   */
  function buildRows(records) {
    var rows = [];
    var errors = [];

    records.forEach(function (record) {
      var values = record.values;
      var rowProblems = [];

      var lineId = (values.line_id || "").trim();
      var description = (values.description || "").trim();
      if (lineId === "") {
        rowProblems.push("line_id is required");
      }

      var quantity = null;
      try {
        quantity = parseQuantity(values.quantity);
      } catch (error) {
        rowProblems.push("quantity " + error.message);
      }

      var unitCostCents = readMoney(values.unit_cost, "unit_cost", rowProblems);
      var allocatedFreightCents = readMoney(
        values.allocated_freight,
        "allocated_freight",
        rowProblems
      );
      var landedUnitCostCents = readMoney(
        values.landed_unit_cost,
        "landed_unit_cost",
        rowProblems
      );

      if (rowProblems.length > 0) {
        rowProblems.forEach(function (problem) {
          errors.push("Line " + record.line + ": " + problem + ".");
        });
        return;
      }

      var goodsValueCents = quantity * unitCostCents;
      var lineLandedCents = goodsValueCents + allocatedFreightCents;

      rows.push({
        lineId: lineId,
        description: description,
        quantity: quantity,
        unitCostCents: unitCostCents,
        allocatedFreightCents: allocatedFreightCents,
        landedUnitCostCents: landedUnitCostCents,
        goodsValueCents: goodsValueCents,
        lineLandedCents: lineLandedCents,
      });
    });

    return { rows: rows, errors: errors };
  }

  function readMoney(raw, column, rowProblems) {
    try {
      var cents = toCents(raw);
      if (cents < 0) {
        rowProblems.push(column + " must be 0 or greater");
        return null;
      }
      return cents;
    } catch (error) {
      rowProblems.push(column + " " + error.message);
      return null;
    }
  }

  /*
   * Total the rows. total freight is the sum of allocated freight; total landed
   * is the sum of per-line landed cost (goods value plus freight). All in cents.
   */
  function summarize(rows) {
    var totalFreightCents = 0;
    var totalGoodsCents = 0;
    var totalLandedCents = 0;
    rows.forEach(function (row) {
      totalFreightCents += row.allocatedFreightCents;
      totalGoodsCents += row.goodsValueCents;
      totalLandedCents += row.lineLandedCents;
    });
    return {
      totalFreightCents: totalFreightCents,
      totalGoodsCents: totalGoodsCents,
      totalLandedCents: totalLandedCents,
      lineCount: rows.length,
    };
  }

  // Format integer cents as a currency string, e.g. 2593 -> "$25.93".
  function formatMoney(cents) {
    return moneyFormatter.format(cents / 100);
  }

  global.DashboardLogic = {
    REQUIRED_COLUMNS: REQUIRED_COLUMNS,
    parseCsv: parseCsv,
    missingColumns: missingColumns,
    toCents: toCents,
    parseQuantity: parseQuantity,
    buildRows: buildRows,
    summarize: summarize,
    formatMoney: formatMoney,
  };
})(typeof window !== "undefined" ? window : this);
