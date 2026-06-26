/*
 * app.js
 *
 * Thin DOM layer for the Volunteer Hours Dashboard. It reads CSV text, hands it
 * to HoursLogic, and renders the totals, milestones, anomalies, and rejected
 * rows. All rules live in hours_logic.js. Uploaded files are read with the
 * FileReader API and never leave the browser.
 */
(function () {
  "use strict";

  // The bundled CSVs, embedded so the sample buttons work offline by
  // double-clicking. They match the files in data/.
  var SAMPLE_CSV = [
    "entry_id,volunteer_id,volunteer_name,date,start_time,end_time",
    "H-101,V-101,Ana Reyes,2026-06-02,09:00,12:00",
    "H-102,V-101,Ana Reyes,2026-06-05,13:00,17:00",
    "H-103,V-101,Ana Reyes,2026-06-09,09:00,12:00",
    "H-104,V-102,Ben Cho,2026-06-01,08:00,16:00",
    "H-105,V-102,Ben Cho,2026-06-03,08:00,16:00",
    "H-106,V-102,Ben Cho,2026-06-06,09:00,14:00",
    "H-107,V-102,Ben Cho,2026-06-10,09:00,15:00",
    "H-108,V-103,Carmen Diaz,2026-06-04,10:00,12:30",
    "H-109,V-103,Carmen Diaz,2026-06-07,10:00,13:00",
    "H-110,V-104,Dev Patel,2026-06-08,09:00,12:00",
    "H-111,V-106,Priya Nair,2026-06-02,09:00,12:00",
    "H-112,V-106,Priya Nair,2026-06-02,13:00,15:00",
    "H-113,V-106,Priya Nair,2026-06-11,09:00,17:00"
  ].join("\n");

  var MESSY_CSV = [
    "entry_id,volunteer_id,volunteer_name,date,start_time,end_time",
    "H-1,V-101,Ana Reyes,2026-06-02,09:00,12:00",
    "H-2,V-101,Ana Reyes,2026-06-02,11:00,13:00",
    "H-3,V-102,Ben Cho,2026-06-03,06:00,19:00",
    "H-9,V-102,Ben Cho,2026-06-03,19:30,22:00",
    "H-4,V-103,Carmen Diaz,2026-06-04,10:00",
    "H-5,V-104,Dev Patel,2026-06-05,9am,12:00",
    "H-1,V-105,Jordan Lee,2026-06-06,09:00,10:00",
    "H-6,V-106,Priya Nair,2026-06-07,09:00,12:00,extra",
    "H-7,V-102,Ben Cho,2026-13-02,09:00,12:00",
    "H-8,V-103,Carmen Diaz,2026-06-08,14:00,13:00"
  ].join("\n");

  var els = {
    loadSample: document.getElementById("loadSample"),
    loadMessy: document.getElementById("loadMessy"),
    csvFile: document.getElementById("csvFile"),
    note: document.getElementById("note"),
    summary: document.getElementById("summary"),
    totalRows: document.getElementById("totalRows"),
    anomaliesBody: document.getElementById("anomaliesBody"),
    rejectedBody: document.getElementById("rejectedBody")
  };

  function run(text) {
    var parsed = HoursLogic.parseCsv(text);
    var result = HoursLogic.summarize(parsed.rows, HoursLogic.DEFAULT_CONFIG);
    render(parsed, result);
  }

  function render(parsed, result) {
    if (parsed.headerError) {
      els.note.hidden = false;
      els.note.textContent = parsed.headerError;
    } else {
      els.note.hidden = true;
      els.note.textContent = "";
    }

    els.totalRows.innerHTML = "";
    result.totals.forEach(function (t) {
      var tr = document.createElement("tr");
      appendCell(tr, t.name + "  (" + t.volunteer_id + ")");
      appendNum(tr, String(t.entries));
      appendNum(tr, t.formatted);

      var td = document.createElement("td");
      if (t.milestone !== null) {
        var badge = document.createElement("span");
        badge.className = "badge badge-milestone";
        badge.textContent = t.milestone + " hour milestone";
        td.appendChild(badge);
      } else {
        var none = document.createElement("span");
        none.className = "badge-none";
        none.textContent = "none yet";
        td.appendChild(none);
      }
      tr.appendChild(td);
      els.totalRows.appendChild(tr);
    });

    renderAnomalies(result.anomalies);
    renderRejected(parsed.rejected);

    var counts = {
      volunteers: result.totals.length,
      entries: result.totals.reduce(function (s, t) { return s + t.entries; }, 0),
      milestones: result.milestones.length,
      anomalies: result.anomalies.length,
      rejected: parsed.rejected.length
    };
    els.summary.textContent =
      counts.entries + " entries across " + counts.volunteers + " volunteers, " +
      counts.milestones + " milestone" + (counts.milestones === 1 ? "" : "s") + ", " +
      counts.anomalies + " anomal" + (counts.anomalies === 1 ? "y" : "ies") + ", " +
      counts.rejected + " row" + (counts.rejected === 1 ? "" : "s") + " rejected";
    els.summary.className = (counts.anomalies + counts.rejected) === 0 ? "clean" : "flagged";
  }

  function renderAnomalies(anomalies) {
    els.anomaliesBody.innerHTML = "";
    if (anomalies.length === 0) {
      els.anomaliesBody.appendChild(emptyNote("No anomalies found."));
      return;
    }
    var ul = document.createElement("ul");
    anomalies.forEach(function (a) {
      var li = document.createElement("li");
      var tag = document.createElement("span");
      tag.className = "anomaly-tag";
      tag.textContent = a.type.replace("-", " ");
      li.appendChild(tag);
      li.appendChild(document.createTextNode(a.name + " (" + a.volunteer_id + "): " + a.detail));
      ul.appendChild(li);
    });
    els.anomaliesBody.appendChild(ul);
  }

  function renderRejected(rejected) {
    els.rejectedBody.innerHTML = "";
    if (rejected.length === 0) {
      els.rejectedBody.appendChild(emptyNote("Every row parsed cleanly."));
      return;
    }
    var ul = document.createElement("ul");
    rejected.forEach(function (r) {
      var li = document.createElement("li");
      li.textContent = "Line " + r.line + ": " + r.reason + "  [" + r.raw + "]";
      ul.appendChild(li);
    });
    els.rejectedBody.appendChild(ul);
  }

  function emptyNote(text) {
    var p = document.createElement("p");
    p.className = "empty";
    p.textContent = text;
    return p;
  }

  function appendCell(tr, text) {
    var td = document.createElement("td");
    td.textContent = text;
    tr.appendChild(td);
  }

  function appendNum(tr, text) {
    var td = document.createElement("td");
    td.className = "num";
    td.textContent = text;
    tr.appendChild(td);
  }

  function handleCsvFile(event) {
    var file = event.target.files && event.target.files[0];
    if (!file) {
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      run(String(reader.result));
    };
    reader.onerror = function () {
      els.note.hidden = false;
      els.note.textContent = "The browser could not read that file.";
    };
    reader.readAsText(file);
    event.target.value = "";
  }

  els.loadSample.addEventListener("click", function () { run(SAMPLE_CSV); });
  els.loadMessy.addEventListener("click", function () { run(MESSY_CSV); });
  els.csvFile.addEventListener("change", handleCsvFile);

  // Start with the sample data loaded.
  run(SAMPLE_CSV);
})();
