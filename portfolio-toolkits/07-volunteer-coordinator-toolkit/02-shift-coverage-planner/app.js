/*
 * app.js
 *
 * Thin DOM layer for the Shift Coverage Planner. It reads the cleared roster,
 * the shifts, and the assignments from the page, hands them to CoverageLogic,
 * and renders the coverage table, the conflicts, and the rejected assignments.
 * All rules live in coverage_logic.js.
 */
(function () {
  "use strict";

  // The cleared roster from the Onboarding Eligibility Validator. Jordan Lee
  // (V-105) is not cleared, so the planner will not let him fill a shift.
  var ROSTER = [
    { id: "V-101", name: "Ana Reyes", cleared: true },
    { id: "V-102", name: "Ben Cho", cleared: true },
    { id: "V-103", name: "Carmen Diaz", cleared: true },
    { id: "V-104", name: "Dev Patel", cleared: true },
    { id: "V-105", name: "Jordan Lee", cleared: false },
    { id: "V-106", name: "Priya Nair", cleared: true }
  ];

  var SAMPLE_SHIFTS = [
    { id: "S-1", role: "Front desk morning", date: "2026-06-13", start: "09:00", end: "12:00", min: 2, max: 3 },
    { id: "S-2", role: "Front desk midday", date: "2026-06-13", start: "12:00", end: "15:00", min: 2, max: 2 },
    { id: "S-3", role: "Greeter", date: "2026-06-13", start: "10:00", end: "13:00", min: 1, max: 2 },
    { id: "S-4", role: "Setup crew", date: "2026-06-13", start: "08:00", end: "10:00", min: 1, max: 1 },
    { id: "S-5", role: "Tear down", date: "2026-06-13", start: "16:00", end: "18:00", min: 1, max: 2 },
    { id: "S-6", role: "Inventory count", date: "2026-06-13", start: "14:00", end: "14:00", min: 1, max: 1 }
  ];

  var SAMPLE_ASSIGNMENTS = [
    { shiftId: "S-1", volunteerId: "V-101" },
    { shiftId: "S-1", volunteerId: "V-102" },
    { shiftId: "S-1", volunteerId: "V-101" },
    { shiftId: "S-2", volunteerId: "V-101" },
    { shiftId: "S-2", volunteerId: "V-106" },
    { shiftId: "S-3", volunteerId: "V-102" },
    { shiftId: "S-3", volunteerId: "V-103" },
    { shiftId: "S-3", volunteerId: "V-104" },
    { shiftId: "S-4", volunteerId: "V-105" },
    { shiftId: "S-5", volunteerId: "V-104" },
    { shiftId: "S-6", volunteerId: "V-103" },
    { shiftId: "S-9", volunteerId: "V-102" }
  ];

  var roster = ROSTER.slice();

  var els = {
    rosterList: document.getElementById("rosterList"),
    shiftRows: document.getElementById("shiftRows"),
    assignmentRows: document.getElementById("assignmentRows"),
    plan: document.getElementById("plan"),
    addShift: document.getElementById("addShift"),
    addAssignment: document.getElementById("addAssignment"),
    loadSample: document.getElementById("loadSample"),
    rosterFile: document.getElementById("rosterFile"),
    summary: document.getElementById("summary"),
    coverageRows: document.getElementById("coverageRows"),
    conflictsBody: document.getElementById("conflictsBody"),
    rejectedBody: document.getElementById("rejectedBody")
  };

  // --- roster ---------------------------------------------------------------

  function renderRoster() {
    els.rosterList.innerHTML = "";
    roster.forEach(function (r) {
      var li = document.createElement("li");
      li.className = r.cleared ? "cleared" : "blocked";
      li.textContent = r.name + " (" + r.id + ") " + (r.cleared ? "cleared" : "blocked");
      els.rosterList.appendChild(li);
    });
  }

  // --- shift and assignment rows -------------------------------------------

  function cell(child) {
    var td = document.createElement("td");
    td.appendChild(child);
    return td;
  }

  function input(className, value) {
    var el = document.createElement("input");
    el.type = "text";
    el.className = className;
    el.value = value === undefined || value === null ? "" : String(value);
    return el;
  }

  function removeButton(row) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "ghost";
    b.textContent = "Remove";
    b.addEventListener("click", function () { row.parentNode.removeChild(row); });
    return b;
  }

  function addShiftRow(shift) {
    var s = shift || {};
    var tr = document.createElement("tr");
    tr.appendChild(cell(input("s-id", s.id)));
    tr.appendChild(cell(input("s-role", s.role)));
    tr.appendChild(cell(input("s-date", s.date)));
    tr.appendChild(cell(input("s-start", s.start)));
    tr.appendChild(cell(input("s-end", s.end)));
    tr.appendChild(cell(input("s-min", s.min)));
    tr.appendChild(cell(input("s-max", s.max)));
    tr.appendChild(cell(removeButton(tr)));
    els.shiftRows.appendChild(tr);
  }

  function addAssignmentRow(a) {
    var assignment = a || {};
    var tr = document.createElement("tr");
    tr.appendChild(cell(input("a-shift", assignment.shiftId)));
    tr.appendChild(cell(input("a-volunteer", assignment.volunteerId)));
    tr.appendChild(cell(removeButton(tr)));
    els.assignmentRows.appendChild(tr);
  }

  function numOrText(value) {
    var t = String(value).trim();
    if (t === "") { return t; }
    return isFinite(Number(t)) ? Number(t) : t;
  }

  function readShifts() {
    return Array.prototype.map.call(els.shiftRows.querySelectorAll("tr"), function (tr) {
      return {
        id: tr.querySelector(".s-id").value.trim(),
        role: tr.querySelector(".s-role").value.trim(),
        date: tr.querySelector(".s-date").value.trim(),
        start: tr.querySelector(".s-start").value.trim(),
        end: tr.querySelector(".s-end").value.trim(),
        min: numOrText(tr.querySelector(".s-min").value),
        max: numOrText(tr.querySelector(".s-max").value)
      };
    });
  }

  function readAssignments() {
    return Array.prototype.map.call(els.assignmentRows.querySelectorAll("tr"), function (tr) {
      return {
        shiftId: tr.querySelector(".a-shift").value.trim(),
        volunteerId: tr.querySelector(".a-volunteer").value.trim()
      };
    });
  }

  function loadSchedule(shifts, assignments) {
    els.shiftRows.innerHTML = "";
    shifts.forEach(addShiftRow);
    els.assignmentRows.innerHTML = "";
    assignments.forEach(addAssignmentRow);
  }

  // --- output ---------------------------------------------------------------

  var STATUS_LABEL = {
    ok: "OK",
    understaffed: "Understaffed",
    overstaffed: "Overstaffed",
    invalid: "Invalid shift"
  };

  function render(result) {
    els.coverageRows.innerHTML = "";
    result.shifts.forEach(function (s) {
      var tr = document.createElement("tr");
      tr.className = "row-" + s.status;

      appendCell(tr, s.role + "  " + s.id);
      appendCell(tr, s.valid ? (s.date + "  " + s.start + " to " + s.end) : (s.start + " to " + s.end));

      var count = document.createElement("td");
      count.className = "count-cell";
      count.textContent = s.valid ? (s.clearedCount + " / " + s.min + ", " + s.max) : "n/a";
      tr.appendChild(count);

      var statusTd = document.createElement("td");
      var badge = document.createElement("span");
      badge.className = "badge badge-" + s.status;
      badge.textContent = STATUS_LABEL[s.status] || s.status;
      statusTd.appendChild(badge);
      if (!s.valid && s.issue) {
        var note = document.createElement("div");
        note.className = "hint";
        note.textContent = s.issue;
        statusTd.appendChild(note);
      }
      tr.appendChild(statusTd);

      var filled = document.createElement("td");
      filled.className = "staffed-names";
      filled.textContent = s.clearedNames.length ? s.clearedNames.join(", ") : "none";
      tr.appendChild(filled);

      els.coverageRows.appendChild(tr);
    });

    renderConflicts(result.conflicts);
    renderRejected(result.rejected);

    var sm = result.summary;
    var problems = sm.understaffed + sm.overstaffed + sm.invalid + sm.conflictCount + sm.rejectedCount;
    els.summary.textContent =
      sm.okCount + " of " + sm.shiftCount + " shifts fully covered, " +
      sm.understaffed + " understaffed, " + sm.overstaffed + " overstaffed, " +
      sm.conflictCount + " double-booked, " + sm.rejectedCount + " assignments rejected";
    els.summary.className = problems === 0 ? "all-clear" : "has-issues";
  }

  function renderConflicts(conflicts) {
    els.conflictsBody.innerHTML = "";
    if (conflicts.length === 0) {
      els.conflictsBody.appendChild(emptyNote("No volunteer is double-booked."));
      return;
    }
    var ul = document.createElement("ul");
    conflicts.forEach(function (c) {
      var li = document.createElement("li");
      li.textContent = c.name + " (" + c.volunteerId + ") is booked on overlapping shifts " +
        c.shiftA + " and " + c.shiftB + " on " + c.date + ".";
      ul.appendChild(li);
    });
    els.conflictsBody.appendChild(ul);
  }

  function renderRejected(rejected) {
    els.rejectedBody.innerHTML = "";
    if (rejected.length === 0) {
      els.rejectedBody.appendChild(emptyNote("No assignments were rejected."));
      return;
    }
    var ul = document.createElement("ul");
    rejected.forEach(function (r) {
      var li = document.createElement("li");
      li.textContent = "Shift " + r.shiftId + ": " + r.reason;
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

  // --- events ---------------------------------------------------------------

  function plan() {
    render(CoverageLogic.planCoverage(readShifts(), readAssignments(), roster));
  }

  function handleRosterFile(event) {
    var file = event.target.files && event.target.files[0];
    if (!file) {
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      var parsed = CoverageLogic.parseRosterJson(String(reader.result));
      if (!parsed.ok) {
        els.summary.textContent = parsed.error;
        els.summary.className = "has-issues";
        return;
      }
      roster = parsed.roster;
      renderRoster();
      plan();
    };
    reader.onerror = function () {
      els.summary.textContent = "The browser could not read that file.";
      els.summary.className = "has-issues";
    };
    reader.readAsText(file);
    event.target.value = "";
  }

  els.plan.addEventListener("click", plan);
  els.addShift.addEventListener("click", function () { addShiftRow(); });
  els.addAssignment.addEventListener("click", function () { addAssignmentRow(); });
  els.loadSample.addEventListener("click", function () {
    roster = ROSTER.slice();
    renderRoster();
    loadSchedule(SAMPLE_SHIFTS, SAMPLE_ASSIGNMENTS);
    plan();
  });
  els.rosterFile.addEventListener("change", handleRosterFile);

  // Start with the sample schedule planned.
  renderRoster();
  loadSchedule(SAMPLE_SHIFTS, SAMPLE_ASSIGNMENTS);
  plan();
})();
