/*
 * DOM wiring for the cost dashboard. This file reads files and paints the page;
 * all of the arithmetic lives in dashboard.js. Files are read with the
 * FileReader API and never sent anywhere.
 */
(function () {
  "use strict";

  var D = Dashboard;

  // Route a loaded CSV to a dataset name by a column only that file carries.
  function classify(header) {
    if (header.indexOf("inventory_value") !== -1) return "perpetual";
    if (header.indexOf("total_batch_cost") !== -1) return "batches";
    if (header.indexOf("gross_margin") !== -1) return "margins";
    if (header.indexOf("excise_duty") !== -1) return "excise";
    if (header.indexOf("counted_qty") !== -1) return "physical";
    return null;
  }

  function headerOf(text) {
    var firstLine = text.replace(/\r\n/g, "\n").split("\n")[0] || "";
    return firstLine.split(",").map(function (s) { return s.trim(); });
  }

  function render(data) {
    var status = document.getElementById("status");
    var missing = [];
    ["perpetual", "batches", "margins", "excise", "physical"].forEach(function (key) {
      if (!data[key]) missing.push(key);
    });
    if (missing.length) {
      status.className = "status error";
      status.textContent =
        "Could not draw the dashboard. Missing data for: " + missing.join(", ") +
        ". Load the matching CSV from the pipeline, or click Load sample data.";
      document.getElementById("dashboard").classList.add("hidden");
      return;
    }
    status.className = "status ok";
    status.textContent = "Showing the period close. All five views drawn from the loaded files.";
    document.getElementById("dashboard").classList.remove("hidden");

    var perpetual = D.parseCsv(data.perpetual);
    var batches = D.parseCsv(data.batches);
    var margins = D.parseCsv(data.margins);
    var excise = D.parseCsv(data.excise);
    var physical = D.parseCsv(data.physical);

    renderValuation(perpetual);
    renderWaterfall(batches);
    renderMargins(margins);
    renderExcise(excise);
    renderVariances(perpetual, physical);
  }

  function bar(widthPct, cssClass) {
    return '<span class="bar ' + (cssClass || "") + '" style="width:' + widthPct + '%"></span>';
  }

  function renderValuation(perpetual) {
    var cats = D.valuationByCategory(perpetual);
    var total = D.totalInventory(perpetual);
    var max = Math.max.apply(null, cats.map(function (c) { return Math.abs(c.valueCents); }).concat([1]));
    document.getElementById("valuation-total").textContent = D.formatMoney(total);
    var html = "";
    cats.forEach(function (c) {
      var pct = (Math.abs(c.valueCents) / max) * 100;
      html +=
        '<div class="row">' +
        '<span class="row-label">' + label(c.category) + "</span>" +
        '<span class="track">' + bar(pct, "accent") + "</span>" +
        '<span class="row-value">' + D.formatMoney(c.valueCents) + "</span>" +
        "</div>";
    });
    document.getElementById("valuation-rows").innerHTML = html;
  }

  function renderWaterfall(batches) {
    var w = D.batchWaterfall(batches);
    var max = w.totalCents || 1;
    var html = "";
    w.steps.forEach(function (step) {
      var offsetPct = (step.startCents / max) * 100;
      var widthPct = (step.valueCents / max) * 100;
      html +=
        '<div class="row">' +
        '<span class="row-label">' + step.label + "</span>" +
        '<span class="track">' +
        '<span class="bar spacer" style="width:' + offsetPct + '%"></span>' +
        bar(widthPct, "accent") +
        "</span>" +
        '<span class="row-value">' + D.formatMoney(step.valueCents) + "</span>" +
        "</div>";
    });
    html +=
      '<div class="row total">' +
      '<span class="row-label">Total batch cost</span>' +
      '<span class="track">' + bar(100, "base") + "</span>" +
      '<span class="row-value">' + D.formatMoney(w.totalCents) + "</span>" +
      "</div>";
    document.getElementById("waterfall-rows").innerHTML = html;
  }

  function renderMargins(margins) {
    var ranked = D.skuMarginRanking(margins);
    var max = Math.max.apply(null, ranked.map(function (r) { return r.marginCents; }).concat([1]));
    var html =
      "<thead><tr><th>SKU</th><th>Line</th><th>Channel</th>" +
      "<th class='num'>Revenue</th><th class='num'>Margin</th><th>Margin %</th></tr></thead><tbody>";
    ranked.forEach(function (r) {
      var pct = (r.marginCents / max) * 100;
      html +=
        "<tr>" +
        "<td>" + r.fg_sku + "</td>" +
        "<td>" + r.product_line + "</td>" +
        "<td>" + label(r.channel) + "</td>" +
        "<td class='num'>" + D.formatMoney(r.revenueCents) + "</td>" +
        "<td class='num'>" + D.formatMoney(r.marginCents) + "</td>" +
        "<td><span class='track inline'>" + bar(pct, "accent") +
        "</span><span class='pct'>" + r.marginPct.toFixed(2) + "%</span></td>" +
        "</tr>";
    });
    html += "</tbody>";
    document.getElementById("margin-table").innerHTML = html;
  }

  function renderExcise(excise) {
    var rows = D.exciseByClass(excise);
    var max = Math.max.apply(null, rows.map(function (r) { return r.dutyCents; }).concat([1]));
    var total = rows.reduce(function (s, r) { return s + r.dutyCents; }, 0);
    var html = "";
    rows.forEach(function (r) {
      var pct = (r.dutyCents / max) * 100;
      html +=
        '<div class="row">' +
        '<span class="row-label">' + label(r.abv_class) + " <em>" + r.hectolitres.toFixed(2) + " hL</em></span>" +
        '<span class="track">' + bar(pct, "accent") + "</span>" +
        '<span class="row-value">' + D.formatMoney(r.dutyCents) + "</span>" +
        "</div>";
    });
    document.getElementById("excise-rows").innerHTML = html;
    document.getElementById("excise-total").textContent = D.formatMoney(total);
  }

  function renderVariances(perpetual, physical) {
    var reconciled = D.reconcile(perpetual, physical);
    var exceptions = D.exceptions(reconciled);
    document.getElementById("exception-count").textContent = exceptions.length;
    var html =
      "<thead><tr><th>SKU</th><th class='num'>Book</th><th class='num'>Counted</th>" +
      "<th class='num'>Qty var</th><th class='num'>Value var</th><th>Status</th></tr></thead><tbody>";
    reconciled.forEach(function (r) {
      var isException = r.status === "over tolerance" || r.integrityFlag !== "";
      var statusText = r.integrityFlag !== "" ? r.integrityFlag : r.status;
      var pill = isException ? "pill flag" : "pill ok";
      html +=
        "<tr class='" + (isException ? "exception" : "") + "'>" +
        "<td>" + r.sku + "</td>" +
        "<td class='num'>" + r.bookQty + "</td>" +
        "<td class='num'>" + r.countedQty + "</td>" +
        "<td class='num'>" + (r.qtyVar > 0 ? "+" : "") + r.qtyVar + "</td>" +
        "<td class='num'>" + D.formatMoney(r.valueVarCents) + "</td>" +
        "<td><span class='" + pill + "'>" + statusText + "</span></td>" +
        "</tr>";
    });
    html += "</tbody>";
    document.getElementById("variance-table").innerHTML = html;
  }

  function label(value) {
    var map = {
      raw_material: "Raw material",
      packaging_material: "Packaging",
      finished_goods: "Finished goods",
      over_2_5: "Over 2.5% ABV",
      over_1_2_to_2_5: "Over 1.2% to 2.5% ABV",
      not_over_1_2: "Not over 1.2% ABV",
      retail: "Retail",
      on_premise: "On-premise",
      distributor: "Distributor",
    };
    return map[value] || value;
  }

  // Wire the controls.
  function init() {
    document.getElementById("sample-btn").addEventListener("click", function () {
      render({
        perpetual: SAMPLE_DATA.perpetual,
        batches: SAMPLE_DATA.batches,
        margins: SAMPLE_DATA.margins,
        excise: SAMPLE_DATA.excise,
        physical: SAMPLE_DATA.physical,
      });
    });

    document.getElementById("file-input").addEventListener("change", function (event) {
      var files = Array.prototype.slice.call(event.target.files);
      if (!files.length) return;
      var data = {};
      var pending = files.length;
      var unknown = [];
      files.forEach(function (file) {
        var reader = new FileReader();
        reader.onload = function () {
          var text = String(reader.result);
          var kind = classify(headerOf(text));
          if (kind) {
            data[kind] = text;
          } else {
            unknown.push(file.name);
          }
          pending -= 1;
          if (pending === 0) {
            if (unknown.length) {
              var status = document.getElementById("status");
              status.className = "status error";
              status.textContent = "Did not recognise: " + unknown.join(", ") +
                ". Expected the pipeline CSVs (valuation, batch costs, margins, excise, counts).";
            }
            render(data);
          }
        };
        reader.readAsText(file);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
