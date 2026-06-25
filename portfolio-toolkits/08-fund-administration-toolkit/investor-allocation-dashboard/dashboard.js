/*
 * Page wiring for the Investor Allocation Dashboard.
 *
 * This file is intentionally thin. It reads the chosen file with FileReader and
 * hands the text to the pure functions in allocation-logic.js, then puts the
 * results into the table and summary. The file is read in the browser only and
 * is never sent anywhere.
 */

(function () {
  var input = document.getElementById("csv-input");
  var message = document.getElementById("message");
  var summary = document.getElementById("summary");
  var table = document.getElementById("allocation-table");
  var tbody = table.querySelector("tbody");

  input.addEventListener("change", function () {
    var file = input.files[0];
    if (!file) {
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      render(reader.result);
    };
    reader.onerror = function () {
      showError("Could not read that file. Please try again.");
    };
    reader.readAsText(file);
  });

  function render(text) {
    try {
      var parsed = parseCsv(text);
      var rows = buildAllocationRows(parsed);
      var totals = summarize(rows);
      drawSummary(totals);
      drawRows(rows, totals.totalCommitment);
      clearMessage();
    } catch (error) {
      showError(error.message);
    }
  }

  function drawSummary(totals) {
    summary.innerHTML = "";
    var items = [
      ["Investors", String(totals.investorCount)],
      ["Total commitment", centsToDisplay(totals.totalCommitment)],
      ["Total called", centsToDisplay(totals.totalCalled)],
      ["Total remaining unfunded", centsToDisplay(totals.totalRemaining)],
    ];
    items.forEach(function (pair) {
      var block = document.createElement("div");
      block.className = "summary__item";

      var label = document.createElement("span");
      label.className = "summary__label";
      label.textContent = pair[0];

      var value = document.createElement("span");
      value.className = "summary__value";
      value.textContent = pair[1];

      block.appendChild(label);
      block.appendChild(value);
      summary.appendChild(block);
    });
    summary.hidden = false;
  }

  function drawRows(rows, totalCommitmentCents) {
    tbody.innerHTML = "";
    rows.forEach(function (row) {
      var remaining = computeRemainingCents(row.commitmentCents, row.calledCents);
      var ownership = computeOwnershipPct(row.commitmentCents, totalCommitmentCents);

      var tr = document.createElement("tr");
      tr.appendChild(textCell(row.investor, false));
      tr.appendChild(textCell(centsToDisplay(row.commitmentCents), true));
      tr.appendChild(textCell(formatPercent(ownership), true));
      tr.appendChild(textCell(centsToDisplay(row.calledCents), true));
      tr.appendChild(textCell(centsToDisplay(remaining), true));
      tbody.appendChild(tr);
    });
    table.hidden = false;
  }

  function textCell(text, numeric) {
    var td = document.createElement("td");
    td.textContent = text;
    if (numeric) {
      td.className = "numeric";
    }
    return td;
  }

  function showError(text) {
    message.textContent = text;
    message.classList.add("message--error");
    summary.hidden = true;
    table.hidden = true;
  }

  function clearMessage() {
    message.textContent = "";
    message.classList.remove("message--error");
  }
})();
