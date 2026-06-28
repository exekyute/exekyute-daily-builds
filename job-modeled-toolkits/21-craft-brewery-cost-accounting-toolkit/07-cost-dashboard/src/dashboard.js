/*
 * Pure logic for the cost dashboard. No DOM access lives here, so the test
 * harness can import these functions and check the numbers directly. Money is
 * carried in integer cents and only formatted for display, so the figures match
 * the Python and SQL tools to the cent.
 *
 * Everything attaches to a single global, Dashboard, so the page works by
 * double-clicking index.html with no module loader and no server.
 */
var Dashboard = (function () {
  "use strict";

  var TOLERANCE_CENTS = 5000; // $50.00 count-variance tolerance

  // Parse a CSV string into an array of row objects keyed by the header.
  // Commas inside quotes are respected; this is enough for the pipeline files.
  function parseCsv(text) {
    var lines = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
    var rows = [];
    var header = null;
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (line.trim() === "") continue;
      var fields = splitLine(line);
      if (header === null) {
        header = fields;
        continue;
      }
      var row = {};
      for (var c = 0; c < header.length; c++) {
        row[header[c]] = (fields[c] === undefined ? "" : fields[c]).trim();
      }
      rows.push(row);
    }
    return rows;
  }

  function splitLine(line) {
    var out = [];
    var current = "";
    var inQuotes = false;
    for (var i = 0; i < line.length; i++) {
      var ch = line[i];
      if (ch === '"') {
        inQuotes = !inQuotes;
      } else if (ch === "," && !inQuotes) {
        out.push(current);
        current = "";
      } else {
        current += ch;
      }
    }
    out.push(current);
    return out;
  }

  // Convert a money string like "1234.56" to integer cents, rounding half up.
  function toCents(value) {
    var n = parseFloat(value);
    if (isNaN(n)) return 0;
    return Math.round(n * 100);
  }

  function toNumber(value) {
    var n = parseFloat(value);
    return isNaN(n) ? 0 : n;
  }

  var moneyFmt = new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
  });

  function formatMoney(cents) {
    return moneyFmt.format(cents / 100);
  }

  function formatCents(cents) {
    // Plain fixed-point dollars, no symbol, for axis-style labels.
    var sign = cents < 0 ? "-" : "";
    var abs = Math.abs(cents);
    return sign + (abs / 100).toFixed(2);
  }

  // Inventory value by category, in first-seen order.
  function valuationByCategory(perpetualRows) {
    var order = [];
    var totals = {};
    perpetualRows.forEach(function (row) {
      var cat = row.category;
      if (!(cat in totals)) {
        totals[cat] = 0;
        order.push(cat);
      }
      totals[cat] += toCents(row.inventory_value);
    });
    return order.map(function (cat) {
      return { category: cat, valueCents: totals[cat] };
    });
  }

  function totalInventory(perpetualRows) {
    return perpetualRows.reduce(function (sum, row) {
      return sum + toCents(row.inventory_value);
    }, 0);
  }

  // Build the cost components for the batch waterfall, summed across batches.
  function batchWaterfall(batchRows) {
    var ingredients = 0, labour = 0, overhead = 0, packaging = 0;
    batchRows.forEach(function (row) {
      ingredients += toCents(row.ingredient_cost);
      labour += toCents(row.labour_cost);
      overhead += toCents(row.overhead_cost);
      packaging += toCents(row.packaging_material_cost);
    });
    var steps = [
      { label: "Ingredients", valueCents: ingredients },
      { label: "Direct labour", valueCents: labour },
      { label: "Overhead", valueCents: overhead },
      { label: "Packaging materials", valueCents: packaging },
    ];
    var running = 0;
    steps.forEach(function (step) {
      step.startCents = running;
      running += step.valueCents;
      step.endCents = running;
    });
    return { steps: steps, totalCents: running };
  }

  // SKU margins ranked by gross margin, highest first.
  function skuMarginRanking(marginRows) {
    var rows = marginRows.map(function (row) {
      return {
        fg_sku: row.fg_sku,
        product_line: row.product_line,
        channel: row.channel,
        revenueCents: toCents(row.revenue),
        cogsCents: toCents(row.cogs_total),
        marginCents: toCents(row.gross_margin),
        marginPct: toNumber(row.margin_pct),
      };
    });
    rows.sort(function (a, b) {
      return b.marginCents - a.marginCents;
    });
    return rows;
  }

  // Excise duty by ABV class.
  function exciseByClass(exciseRows) {
    return exciseRows.map(function (row) {
      return {
        abv_class: row.abv_class,
        hectolitres: toNumber(row.hectolitres),
        dutyCents: toCents(row.excise_duty),
      };
    });
  }

  // Reconcile book inventory against the physical count. Mirrors the SQL close:
  // value variance is the quantity variance times the weighted-average cost, and
  // anything past the $50.00 tolerance is flagged.
  function reconcile(perpetualRows, physicalRows) {
    var counts = {};
    physicalRows.forEach(function (row) {
      counts[row.sku] = toNumber(row.counted_qty);
    });
    var out = [];
    perpetualRows.forEach(function (row) {
      if (!(row.sku in counts)) return;
      var book = toNumber(row.on_hand_qty);
      var counted = counts[row.sku];
      var qtyVar = counted - book;
      var wac = toNumber(row.wac_unit_cost);
      var valueVarCents = Math.round(qtyVar * wac * 100);
      var overTolerance = Math.abs(valueVarCents) > TOLERANCE_CENTS;
      out.push({
        sku: row.sku,
        category: row.category,
        bookQty: book,
        countedQty: counted,
        qtyVar: qtyVar,
        valueVarCents: valueVarCents,
        status: overTolerance ? "over tolerance" : "within tolerance",
        integrityFlag: row.integrity_flag || "",
      });
    });
    out.sort(function (a, b) {
      return Math.abs(b.valueVarCents) - Math.abs(a.valueVarCents);
    });
    return out;
  }

  function exceptions(reconciled) {
    return reconciled.filter(function (r) {
      return r.status === "over tolerance" || r.integrityFlag !== "";
    });
  }

  return {
    TOLERANCE_CENTS: TOLERANCE_CENTS,
    parseCsv: parseCsv,
    toCents: toCents,
    toNumber: toNumber,
    formatMoney: formatMoney,
    formatCents: formatCents,
    valuationByCategory: valuationByCategory,
    totalInventory: totalInventory,
    batchWaterfall: batchWaterfall,
    skuMarginRanking: skuMarginRanking,
    exciseByClass: exciseByClass,
    reconcile: reconcile,
    exceptions: exceptions,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = Dashboard;
}
