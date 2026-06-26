/*
 * app.js
 *
 * Thin DOM layer for the Comp Plan Rule Validator. It reads the plan from the
 * form, hands it to ValidatorLogic, and renders the findings. All rules live in
 * validator_logic.js.
 */
(function () {
  "use strict";

  // The approved sample. It is byte-for-byte the same plan the Tiered
  // Commission Calculator ships, so a pass here means the two tools agree.
  var SAMPLE_PLAN = {
    planName: "FY26 Field Sales Commission Plan",
    quota: 80000,
    accelerator: 1.5,
    tiers: [
      { label: "Tier 1", from: 0, to: 50000, rate: 5 },
      { label: "Tier 2", from: 50000, to: 100000, rate: 8 },
      { label: "Tier 3", from: 100000, to: null, rate: 10 }
    ]
  };

  // A plan that trips one of every flag, for demonstration.
  var BROKEN_PLAN = {
    planName: "Draft plan with problems",
    quota: 0,
    accelerator: 0.8,
    tiers: [
      { label: "Tier 1", from: 0, to: 50000, rate: 5 },
      { label: "Tier 2", from: 50000, to: 100000, rate: 0 },
      { label: "Tier 3", from: 90000, to: 80000, rate: -3 },
      { label: "Tier 4", from: 120000, to: null, rate: 8 }
    ]
  };

  var els = {
    planName: document.getElementById("planName"),
    quota: document.getElementById("quota"),
    accelerator: document.getElementById("accelerator"),
    tierRows: document.getElementById("tierRows"),
    addTier: document.getElementById("addTier"),
    loadSample: document.getElementById("loadSample"),
    loadBroken: document.getElementById("loadBroken"),
    planFile: document.getElementById("planFile"),
    validate: document.getElementById("validate"),
    approved: document.getElementById("approved"),
    findings: document.getElementById("findings"),
    findingsHeading: document.getElementById("findingsHeading"),
    findingRows: document.getElementById("findingRows")
  };

  // --- plan in and out of the form -----------------------------------------

  function addTierRow(tier) {
    tier = tier || { label: "", from: "", to: "", rate: "" };
    var tr = document.createElement("tr");
    tr.appendChild(cell(textInput("tier-label", tier.label)));
    tr.appendChild(cell(textInput("tier-from", numOrEmpty(tier.from))));
    tr.appendChild(cell(textInput("tier-to", tier.to === null || tier.to === undefined ? "" : tier.to)));
    tr.appendChild(cell(textInput("tier-rate", numOrEmpty(tier.rate))));

    var remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost danger";
    remove.textContent = "Remove";
    remove.addEventListener("click", function () {
      tr.parentNode.removeChild(tr);
    });
    tr.appendChild(cell(remove));
    els.tierRows.appendChild(tr);
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

  function numOrEmpty(value) {
    return value === undefined || value === null || value === "" ? "" : value;
  }

  function loadPlanIntoForm(plan) {
    els.planName.value = plan.planName || "";
    els.quota.value = plan.quota === undefined || plan.quota === null ? "" : plan.quota;
    els.accelerator.value =
      plan.accelerator === undefined || plan.accelerator === null ? "" : plan.accelerator;
    els.tierRows.innerHTML = "";
    (plan.tiers || []).forEach(addTierRow);
  }

  function readPlanFromForm() {
    var rows = els.tierRows.querySelectorAll("tr");
    var tiers = [];
    rows.forEach(function (tr) {
      var fromText = tr.querySelector(".tier-from").value.trim();
      var toText = tr.querySelector(".tier-to").value.trim();
      var rateText = tr.querySelector(".tier-rate").value.trim();
      tiers.push({
        label: tr.querySelector(".tier-label").value.trim(),
        from: fromText === "" ? fromText : Number(fromText),
        to: toText === "" ? null : Number(toText),
        rate: rateText === "" ? rateText : Number(rateText)
      });
    });
    var quotaText = els.quota.value.trim();
    var accelText = els.accelerator.value.trim();
    return {
      planName: els.planName.value.trim(),
      quota: quotaText === "" ? quotaText : Number(quotaText),
      accelerator: accelText === "" ? accelText : Number(accelText),
      tiers: tiers
    };
  }

  // --- output ---------------------------------------------------------------

  function render(result) {
    if (result.approved && result.findings.length === 0) {
      els.findings.hidden = true;
      els.approved.hidden = false;
      return;
    }

    els.approved.hidden = true;
    els.findingRows.innerHTML = "";
    result.findings.forEach(function (f) {
      var tr = document.createElement("tr");
      tr.className = "row-" + f.severity;

      var sev = document.createElement("td");
      var badge = document.createElement("span");
      badge.className = "badge badge-" + f.severity;
      badge.textContent = f.severity === "error" ? "Error" : "Warning";
      sev.appendChild(badge);
      tr.appendChild(sev);

      appendCell(tr, f.location);
      appendCell(tr, f.message);
      els.findingRows.appendChild(tr);
    });

    var errors = ValidatorLogic.countBySeverity(result.findings, "error");
    var warnings = ValidatorLogic.countBySeverity(result.findings, "warning");
    var parts = [];
    if (errors > 0) {
      parts.push(errors + (errors === 1 ? " error" : " errors"));
    }
    if (warnings > 0) {
      parts.push(warnings + (warnings === 1 ? " warning" : " warnings"));
    }
    els.findingsHeading.textContent =
      (result.approved ? "Plan approved with notes: " : "Plan not approved: ") + parts.join(", ");
    els.findings.hidden = false;
  }

  function appendCell(tr, text) {
    var td = document.createElement("td");
    td.textContent = text;
    tr.appendChild(td);
  }

  // --- events ---------------------------------------------------------------

  function validate() {
    render(ValidatorLogic.validate(readPlanFromForm()));
  }

  function handlePlanFile(event) {
    var file = event.target.files && event.target.files[0];
    if (!file) {
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      var parsed = ValidatorLogic.parsePlanJson(String(reader.result));
      if (!parsed.ok) {
        render({ approved: false, findings: [{ severity: "error", code: "json", location: "File", message: parsed.error }] });
        return;
      }
      loadPlanIntoForm(parsed.plan);
      validate();
    };
    reader.onerror = function () {
      render({ approved: false, findings: [{ severity: "error", code: "read", location: "File", message: "The browser could not read that file." }] });
    };
    reader.readAsText(file);
    event.target.value = "";
  }

  els.validate.addEventListener("click", validate);
  els.addTier.addEventListener("click", function () { addTierRow(); });
  els.loadSample.addEventListener("click", function () { loadPlanIntoForm(SAMPLE_PLAN); });
  els.loadBroken.addEventListener("click", function () { loadPlanIntoForm(BROKEN_PLAN); });
  els.planFile.addEventListener("change", handlePlanFile);

  // Start with the approved sample loaded.
  loadPlanIntoForm(SAMPLE_PLAN);
})();
