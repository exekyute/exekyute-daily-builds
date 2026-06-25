/*
 * DOM wiring for the Loan Balance Dashboard.
 *
 * This file is deliberately thin. It reads the chosen file with the FileReader
 * API, hands the text to parseSchedule() in balance-logic.js, and renders the
 * result. All parsing and money math lives in the logic file; this file only
 * moves data between the page and that logic. Nothing is ever sent anywhere.
 */

(function () {
  var fileInput = document.getElementById("file-input");
  var status = document.getElementById("status");
  var errorBox = document.getElementById("errors");
  var summary = document.getElementById("summary");
  var tableWrap = document.getElementById("table-wrap");
  var tableBody = document.getElementById("schedule-body");

  function clearOutput() {
    errorBox.hidden = true;
    errorBox.innerHTML = "";
    summary.hidden = true;
    summary.innerHTML = "";
    tableWrap.hidden = true;
    tableBody.innerHTML = "";
  }

  function showErrors(messages) {
    var heading = document.createElement("p");
    heading.className = "errors-heading";
    heading.textContent = "This file could not be loaded:";
    errorBox.appendChild(heading);

    var list = document.createElement("ul");
    messages.forEach(function (message) {
      var item = document.createElement("li");
      item.textContent = message;
      list.appendChild(item);
    });
    errorBox.appendChild(list);
    errorBox.hidden = false;
  }

  function renderSummary(totals) {
    var fields = [
      { label: "Periods", value: String(totals.periods) },
      { label: "Total interest paid", value: totals.totalInterest },
      { label: "Total of payments", value: totals.totalPayment },
      { label: "Final balance", value: totals.finalBalance },
    ];
    fields.forEach(function (field) {
      var cell = document.createElement("div");
      cell.className = "summary-cell";

      var label = document.createElement("span");
      label.className = "summary-label";
      label.textContent = field.label;

      var value = document.createElement("span");
      value.className = "summary-value";
      value.textContent = field.value;

      cell.appendChild(label);
      cell.appendChild(value);
      summary.appendChild(cell);
    });
    summary.hidden = false;
  }

  function renderRows(rows) {
    rows.forEach(function (row) {
      var tr = document.createElement("tr");
      var cells = [
        { text: String(row.period), money: false },
        { text: row.payment, money: true },
        { text: row.interest, money: true },
        { text: row.principal, money: true },
        { text: row.balance, money: true },
      ];
      cells.forEach(function (cell) {
        var td = document.createElement("td");
        td.textContent = cell.text;
        if (cell.money) {
          td.className = "money";
        }
        tr.appendChild(td);
      });
      tableBody.appendChild(tr);
    });
    tableWrap.hidden = false;
  }

  function handleFile(file) {
    clearOutput();
    status.textContent = "Reading " + file.name + "...";

    var reader = new FileReader();
    reader.onload = function (event) {
      var result = parseSchedule(event.target.result);
      if (!result.ok) {
        status.textContent = "Could not load " + file.name + ".";
        showErrors(result.errors);
        return;
      }
      status.textContent =
        "Loaded " + file.name + " (" + result.totals.periods + " periods).";
      renderSummary(result.totals);
      renderRows(result.rows);
    };
    reader.onerror = function () {
      status.textContent = "Could not read the file.";
      showErrors(["The browser could not read this file."]);
    };
    reader.readAsText(file);
  }

  fileInput.addEventListener("change", function (event) {
    var file = event.target.files[0];
    if (file) {
      handleFile(file);
    }
  });
})();
