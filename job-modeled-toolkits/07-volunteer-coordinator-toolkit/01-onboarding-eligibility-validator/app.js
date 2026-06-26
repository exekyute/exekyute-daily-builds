/*
 * app.js
 *
 * Thin DOM layer for the Onboarding Eligibility Validator. It reads the config
 * and the volunteers from the form, hands them to EligibilityLogic, and renders
 * the results and the cleared roster. All rules live in eligibility_logic.js.
 */
(function () {
  "use strict";

  // The realistic sample roster. Five volunteers clear; Jordan Lee (V-105) is
  // blocked for a missing background check. Evaluating this roster produces the
  // cleared_roster.json that the Shift Coverage Planner ships.
  var SAMPLE = {
    config: {
      as_of_date: "2026-06-01",
      minimum_age: 18,
      required_trainings: ["ORIENT", "SAFETY"],
      background_check_valid_days: 365,
      waiver_valid_days: 365
    },
    volunteers: [
      { id: "V-101", name: "Ana Reyes", date_of_birth: "1990-03-15", background_check: { status: "passed", date: "2026-01-10" }, trainings_completed: ["ORIENT", "SAFETY"], waiver_signed_date: "2026-01-10" },
      { id: "V-102", name: "Ben Cho", date_of_birth: "1985-11-02", background_check: { status: "passed", date: "2025-12-01" }, trainings_completed: ["ORIENT", "SAFETY"], waiver_signed_date: "2025-12-01" },
      { id: "V-103", name: "Carmen Diaz", date_of_birth: "2000-07-20", background_check: { status: "passed", date: "2026-02-14" }, trainings_completed: ["ORIENT", "SAFETY"], waiver_signed_date: "2026-02-14" },
      { id: "V-104", name: "Dev Patel", date_of_birth: "2008-06-01", background_check: { status: "passed", date: "2025-09-15" }, trainings_completed: ["ORIENT", "SAFETY"], waiver_signed_date: "2025-09-15" },
      { id: "V-105", name: "Jordan Lee", date_of_birth: "1998-04-22", background_check: { status: "none", date: "" }, trainings_completed: ["ORIENT", "SAFETY"], waiver_signed_date: "2026-01-05" },
      { id: "V-106", name: "Priya Nair", date_of_birth: "1995-08-30", background_check: { status: "passed", date: "2025-06-01" }, trainings_completed: ["ORIENT", "SAFETY"], waiver_signed_date: "2025-06-01" }
    ]
  };

  // A roster where each volunteer trips a flag, so one load shows every rule.
  var FLAGGED = {
    config: SAMPLE.config,
    volunteers: [
      { id: "V-301", name: "Min Ortiz", date_of_birth: "2012-05-01", background_check: { status: "passed", date: "2026-03-01" }, trainings_completed: ["ORIENT", "SAFETY"], waiver_signed_date: "2026-03-01" },
      { id: "V-302", name: "Lee Park", date_of_birth: "1990-09-09", background_check: { status: "none", date: "" }, trainings_completed: ["ORIENT", "SAFETY"], waiver_signed_date: "2026-03-01" },
      { id: "V-303", name: "Sam Ray", date_of_birth: "1988-01-19", background_check: { status: "failed", date: "2026-03-01" }, trainings_completed: ["ORIENT", "SAFETY"], waiver_signed_date: "2026-03-01" },
      { id: "V-304", name: "Tess Vo", date_of_birth: "1991-06-06", background_check: { status: "passed", date: "2024-05-01" }, trainings_completed: ["ORIENT"], waiver_signed_date: "2026-03-01" },
      { id: "V-305", name: "Uma Shah", date_of_birth: "1993-10-12", background_check: { status: "passed", date: "2026-03-01" }, trainings_completed: ["ORIENT", "SAFETY"], waiver_signed_date: "" },
      { id: "V-306", name: "Will Tan", date_of_birth: "1987-02-28", background_check: { status: "passed", date: "2026-03-01" }, trainings_completed: ["ORIENT", "SAFETY"], waiver_signed_date: "2024-01-01" },
      { id: "V-306", name: "", date_of_birth: "not-a-date", background_check: { status: "passed", date: "2026-03-01" }, trainings_completed: ["ORIENT", "SAFETY"], waiver_signed_date: "2026-03-01" },
      { id: "", name: "Pat Vue", date_of_birth: "1992-02-02", background_check: { status: "passed", date: "2024-13-01" }, trainings_completed: ["ORIENT", "SAFETY"], waiver_signed_date: "01-01-2024" }
    ]
  };

  var els = {
    asOfDate: document.getElementById("asOfDate"),
    minimumAge: document.getElementById("minimumAge"),
    requiredTrainings: document.getElementById("requiredTrainings"),
    bgValidDays: document.getElementById("bgValidDays"),
    waiverValidDays: document.getElementById("waiverValidDays"),
    volunteerRows: document.getElementById("volunteerRows"),
    validate: document.getElementById("validate"),
    addVolunteer: document.getElementById("addVolunteer"),
    loadSample: document.getElementById("loadSample"),
    loadFlagged: document.getElementById("loadFlagged"),
    rosterFile: document.getElementById("rosterFile"),
    summary: document.getElementById("summary"),
    resultRows: document.getElementById("resultRows"),
    rosterJson: document.getElementById("rosterJson")
  };

  // --- config in and out ----------------------------------------------------

  function readConfig() {
    return {
      as_of_date: els.asOfDate.value.trim(),
      minimum_age: els.minimumAge.value.trim(),
      required_trainings: splitList(els.requiredTrainings.value),
      background_check_valid_days: els.bgValidDays.value.trim(),
      waiver_valid_days: els.waiverValidDays.value.trim()
    };
  }

  function loadConfig(config) {
    if (!config) {
      return;
    }
    if (config.as_of_date) { els.asOfDate.value = config.as_of_date; }
    if (config.minimum_age !== undefined) { els.minimumAge.value = config.minimum_age; }
    if (Array.isArray(config.required_trainings)) {
      els.requiredTrainings.value = config.required_trainings.join(", ");
    }
    if (config.background_check_valid_days !== undefined) {
      els.bgValidDays.value = config.background_check_valid_days;
    }
    if (config.waiver_valid_days !== undefined) {
      els.waiverValidDays.value = config.waiver_valid_days;
    }
  }

  function splitList(text) {
    return String(text || "")
      .split(",")
      .map(function (s) { return s.trim(); })
      .filter(function (s) { return s !== ""; });
  }

  // --- volunteers in and out of the form ------------------------------------

  function addVolunteerRow(volunteer) {
    var v = volunteer || {};
    var bg = v.background_check || {};
    var tr = document.createElement("tr");
    tr.appendChild(cell(textInput("col-id", v.id)));
    tr.appendChild(cell(textInput("col-name", v.name)));
    tr.appendChild(cell(textInput("col-dob", v.date_of_birth)));
    tr.appendChild(cell(textInput("col-bgstatus", bg.status)));
    tr.appendChild(cell(textInput("col-bgdate", bg.date)));
    tr.appendChild(cell(textInput("col-trainings", (v.trainings_completed || []).join(", "))));
    tr.appendChild(cell(textInput("col-waiver", v.waiver_signed_date)));

    var remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost";
    remove.textContent = "Remove";
    remove.addEventListener("click", function () {
      tr.parentNode.removeChild(tr);
    });
    tr.appendChild(cell(remove));
    els.volunteerRows.appendChild(tr);
  }

  function cell(child) {
    var td = document.createElement("td");
    td.appendChild(child);
    return td;
  }

  function textInput(className, value) {
    var input = document.createElement("input");
    input.type = "text";
    input.className = className;
    input.value = value === undefined || value === null ? "" : String(value);
    return input;
  }

  function loadRosterIntoForm(roster) {
    loadConfig(roster.config);
    els.volunteerRows.innerHTML = "";
    (roster.volunteers || []).forEach(addVolunteerRow);
  }

  function readVolunteersFromForm() {
    var rows = els.volunteerRows.querySelectorAll("tr");
    var volunteers = [];
    rows.forEach(function (tr) {
      volunteers.push({
        id: tr.querySelector(".col-id").value.trim(),
        name: tr.querySelector(".col-name").value.trim(),
        date_of_birth: tr.querySelector(".col-dob").value.trim(),
        background_check: {
          status: tr.querySelector(".col-bgstatus").value.trim(),
          date: tr.querySelector(".col-bgdate").value.trim()
        },
        trainings_completed: splitList(tr.querySelector(".col-trainings").value),
        waiver_signed_date: tr.querySelector(".col-waiver").value.trim()
      });
    });
    return volunteers;
  }

  // --- output ---------------------------------------------------------------

  function render(rosterResult) {
    els.resultRows.innerHTML = "";
    rosterResult.results.forEach(function (r) {
      var tr = document.createElement("tr");
      if (!r.cleared) {
        tr.className = "row-blocked";
      }

      appendCell(tr, (r.name || "(no name)") + (r.id ? "  " + r.id : ""));

      var statusTd = document.createElement("td");
      var badge = document.createElement("span");
      badge.className = "badge " + (r.cleared ? "badge-cleared" : "badge-blocked");
      badge.textContent = r.cleared ? "Cleared" : "Blocked";
      statusTd.appendChild(badge);
      tr.appendChild(statusTd);

      var reasonsTd = document.createElement("td");
      if (r.findings.length === 0) {
        var ok = document.createElement("ul");
        ok.className = "reasons none";
        var li = document.createElement("li");
        li.textContent = "All requirements met.";
        ok.appendChild(li);
        reasonsTd.appendChild(ok);
      } else {
        var ul = document.createElement("ul");
        ul.className = "reasons";
        r.findings.forEach(function (f) {
          var item = document.createElement("li");
          item.textContent = f.message;
          ul.appendChild(item);
        });
        reasonsTd.appendChild(ul);
      }
      tr.appendChild(reasonsTd);
      els.resultRows.appendChild(tr);
    });

    var s = rosterResult.summary;
    els.summary.textContent =
      s.clearedCount + " of " + s.total + " cleared, " + s.blockedCount + " blocked";
    els.summary.className = s.blockedCount === 0 ? "all-clear" : "has-blocked";

    var roster = EligibilityLogic.toClearedRoster(rosterResult);
    els.rosterJson.textContent = JSON.stringify(roster, null, 2);
  }

  function appendCell(tr, text) {
    var td = document.createElement("td");
    td.textContent = text;
    tr.appendChild(td);
  }

  // --- events ---------------------------------------------------------------

  function validate() {
    var result = EligibilityLogic.evaluateRoster(readVolunteersFromForm(), readConfig());
    render(result);
  }

  function handleRosterFile(event) {
    var file = event.target.files && event.target.files[0];
    if (!file) {
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      var parsed = EligibilityLogic.parseVolunteersJson(String(reader.result));
      if (!parsed.ok) {
        els.summary.textContent = parsed.error;
        els.summary.className = "has-blocked";
        return;
      }
      loadRosterIntoForm({ config: parsed.config, volunteers: parsed.volunteers });
      validate();
    };
    reader.onerror = function () {
      els.summary.textContent = "The browser could not read that file.";
      els.summary.className = "has-blocked";
    };
    reader.readAsText(file);
    event.target.value = "";
  }

  els.validate.addEventListener("click", validate);
  els.addVolunteer.addEventListener("click", function () { addVolunteerRow(); });
  els.loadSample.addEventListener("click", function () { loadRosterIntoForm(SAMPLE); validate(); });
  els.loadFlagged.addEventListener("click", function () { loadRosterIntoForm(FLAGGED); validate(); });
  els.rosterFile.addEventListener("change", handleRosterFile);

  // Start with the sample roster loaded and checked.
  loadRosterIntoForm(SAMPLE);
  validate();
})();
