/*
 * DOM wiring for the Net Pay Dashboard.
 *
 * This file only reads the chosen file and updates the page. All parsing,
 * validation, and money math live in dashboard_logic.js. The file is read
 * with the FileReader API and is never uploaded or sent anywhere.
 */

(function () {
  var fileInput = document.getElementById("fileInput");
  var status = document.getElementById("status");
  var messages = document.getElementById("messages");

  var summaryPanel = document.getElementById("summaryPanel");
  var summaryCount = document.getElementById("summaryCount");
  var summaryGross = document.getElementById("summaryGross");
  var summaryNet = document.getElementById("summaryNet");

  var tablePanel = document.getElementById("tablePanel");
  var registerBody = document.getElementById("registerBody");

  fileInput.addEventListener("change", function (event) {
    var file = event.target.files[0];
    if (!file) {
      return;
    }

    var reader = new FileReader();
    reader.onload = function () {
      handleText(reader.result, file.name);
    };
    reader.onerror = function () {
      showStatus("Could not read the file.");
      hideResults();
    };
    reader.readAsText(file);
  });

  function handleText(text, fileName) {
    var result = parseRegister(text);

    if (result.headerErrors.length > 0) {
      showStatus("This file is not a payroll register.");
      showMessages(result.headerErrors);
      hideResults();
      return;
    }

    renderTable(result.records);
    renderSummary(result.records);

    var note = "Loaded " + result.records.length + " employee(s) from " + fileName + ".";
    if (result.rowErrors.length > 0) {
      note += " " + result.rowErrors.length + " row(s) skipped.";
      showMessages(result.rowErrors);
    } else {
      hideMessages();
    }
    showStatus(note);
  }

  function renderTable(records) {
    registerBody.innerHTML = "";

    records.forEach(function (record) {
      var row = document.createElement("tr");
      row.appendChild(employeeCell(record));
      row.appendChild(textCell(record.payType));
      row.appendChild(moneyCell(record.grossCents));
      row.appendChild(moneyCell(record.overtimeCents));
      row.appendChild(moneyCell(record.totalDeductionsCents));
      row.appendChild(moneyCell(record.incomeTaxCents));
      row.appendChild(moneyCell(record.netCents, "net"));
      registerBody.appendChild(row);
    });

    tablePanel.hidden = records.length === 0;
  }

  function renderSummary(records) {
    var totals = summarize(records);
    summaryCount.textContent = String(records.length);
    summaryGross.textContent = formatCad(totals.totalGrossCents);
    summaryNet.textContent = formatCad(totals.totalNetCents);
    summaryPanel.hidden = records.length === 0;
  }

  function employeeCell(record) {
    var cell = document.createElement("td");
    var name = document.createElement("span");
    name.className = "employee-name";
    name.textContent = record.name;
    var id = document.createElement("span");
    id.className = "employee-id";
    id.textContent = record.employeeId;
    cell.appendChild(name);
    cell.appendChild(id);
    return cell;
  }

  function textCell(value) {
    var cell = document.createElement("td");
    cell.textContent = value;
    return cell;
  }

  function moneyCell(cents, extraClass) {
    var cell = document.createElement("td");
    cell.className = "num" + (extraClass ? " " + extraClass : "");
    cell.textContent = formatCad(cents);
    return cell;
  }

  function showStatus(text) {
    status.textContent = text;
  }

  function showMessages(items) {
    messages.innerHTML = "";
    items.forEach(function (item) {
      var entry = document.createElement("li");
      entry.textContent = item;
      messages.appendChild(entry);
    });
    messages.hidden = false;
  }

  function hideMessages() {
    messages.hidden = true;
    messages.innerHTML = "";
  }

  function hideResults() {
    summaryPanel.hidden = true;
    tablePanel.hidden = true;
    registerBody.innerHTML = "";
  }
})();
