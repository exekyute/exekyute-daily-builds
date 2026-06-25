/*
 * DOM wiring for the Collections Aging Dashboard.
 *
 * This file is intentionally thin. It reads the chosen file with the FileReader
 * API, hands the text to the pure functions in aging-logic.js, and renders the
 * results. No data is sent anywhere. All parsing and totals live in aging-logic.js.
 */

(function () {
  var fileInput = document.getElementById("file-input");
  var message = document.getElementById("message");
  var results = document.getElementById("results");
  var summary = document.getElementById("summary");
  var skippedNotice = document.getElementById("skipped-notice");
  var invoiceRows = document.getElementById("invoice-rows");

  fileInput.addEventListener("change", function (event) {
    var file = event.target.files[0];
    if (!file) {
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      handleText(reader.result);
    };
    reader.onerror = function () {
      showMessage("Could not read that file. Please try again.");
    };
    reader.readAsText(file);
  });

  function handleText(text) {
    var parsed = parseAgingCsv(text);

    if (parsed.error) {
      results.hidden = true;
      showMessage(parsed.error);
      return;
    }

    hideMessage();
    renderSummary(parsed.rows);
    renderRows(parsed.rows);
    renderSkipped(parsed.skipped);
    results.hidden = false;
  }

  function renderSummary(rows) {
    var totals = bucketTotals(rows);
    summary.innerHTML = "";

    BUCKETS.forEach(function (bucket) {
      var entry = totals[bucket];
      var card = document.createElement("div");
      card.className = "summary-card " + bucketClass(bucket);
      card.appendChild(makeLine("card-label", bucket));
      card.appendChild(makeLine("card-total", formatMoney(entry.totalCents)));
      card.appendChild(
        makeLine("card-count", entry.count + (entry.count === 1 ? " invoice" : " invoices"))
      );
      summary.appendChild(card);
    });

    var grand = document.createElement("div");
    grand.className = "summary-card grand";
    grand.appendChild(makeLine("card-label", "Grand total"));
    grand.appendChild(makeLine("card-total", formatMoney(grandTotalCents(rows))));
    grand.appendChild(
      makeLine("card-count", rows.length + (rows.length === 1 ? " invoice" : " invoices"))
    );
    summary.appendChild(grand);
  }

  function renderRows(rows) {
    invoiceRows.innerHTML = "";
    rows.forEach(function (row) {
      var tr = document.createElement("tr");
      tr.className = bucketClass(row.bucket);

      tr.appendChild(makeCell(row.invoiceNumber));
      tr.appendChild(makeCell(row.customer));
      tr.appendChild(makeCell(formatMoney(row.amountCents), "num"));
      tr.appendChild(makeCell(String(row.daysPastDue), "num"));

      var bucketCell = document.createElement("td");
      var tag = document.createElement("span");
      tag.className = "bucket-tag";
      tag.textContent = row.bucket;
      bucketCell.appendChild(tag);
      tr.appendChild(bucketCell);

      tr.appendChild(makeCell(formatMoney(row.lateFeeCents), "num"));
      tr.appendChild(makeCell(formatMoney(row.totalDueCents), "num"));

      invoiceRows.appendChild(tr);
    });
  }

  function renderSkipped(skipped) {
    if (skipped > 0) {
      skippedNotice.textContent =
        skipped + (skipped === 1 ? " row was" : " rows were") +
        " skipped because they were malformed.";
      skippedNotice.hidden = false;
    } else {
      skippedNotice.hidden = true;
    }
  }

  function makeCell(text, extraClass) {
    var td = document.createElement("td");
    if (extraClass) {
      td.className = extraClass;
    }
    td.textContent = text;
    return td;
  }

  function makeLine(className, text) {
    var span = document.createElement("span");
    span.className = className;
    span.textContent = text;
    return span;
  }

  function showMessage(text) {
    message.textContent = text;
    message.hidden = false;
  }

  function hideMessage() {
    message.hidden = true;
    message.textContent = "";
  }
})();
