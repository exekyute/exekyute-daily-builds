/*
 * app.js
 *
 * Thin DOM layer for the Tiered Commission Calculator. It reads the form,
 * hands plain values to CommissionLogic, and renders what comes back. It holds
 * no business rules of its own; all parsing, validation, and money math live in
 * commission_logic.js.
 */
(function () {
  "use strict";

  // The embedded default plan. It matches data/sample_plan.json so the tool
  // works the moment it is opened, with no file load required. The committed
  // JSON file is the same plan the Comp Plan Rule Validator approves.
  var DEFAULT_PLAN = {
    planName: "FY26 Field Sales Commission Plan",
    quota: 80000,
    accelerator: 1.5,
    tiers: [
      { label: "Tier 1", from: 0, to: 50000, rate: 5 },
      { label: "Tier 2", from: 50000, to: 100000, rate: 8 },
      { label: "Tier 3", from: 100000, to: null, rate: 10 }
    ]
  };

  var els = {
    revenue: document.getElementById("revenue"),
    planName: document.getElementById("planName"),
    quota: document.getElementById("quota"),
    accelerator: document.getElementById("accelerator"),
    tierRows: document.getElementById("tierRows"),
    addTier: document.getElementById("addTier"),
    loadSample: document.getElementById("loadSample"),
    planFile: document.getElementById("planFile"),
    calculate: document.getElementById("calculate"),
    problems: document.getElementById("problems"),
    problemList: document.getElementById("problemList"),
    results: document.getElementById("results"),
    resultSummary: document.getElementById("resultSummary"),
    resultRows: document.getElementById("resultRows"),
    resultTotal: document.getElementById("resultTotal")
  };

  // --- rendering the editable plan into the form ----------------------------

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

  // --- reading the plan back out of the form --------------------------------

  function readPlanFromForm() {
    var rows = els.tierRows.querySelectorAll("tr");
    var tiers = [];
    rows.forEach(function (tr, index) {
      var label = tr.querySelector(".tier-label").value.trim() || "Tier " + (index + 1);
      var fromText = tr.querySelector(".tier-from").value.trim();
      var toText = tr.querySelector(".tier-to").value.trim();
      var rateText = tr.querySelector(".tier-rate").value.trim();
      tiers.push({
        label: label,
        from: fromText === "" ? NaN : Number(fromText),
        to: toText === "" ? null : Number(toText),
        rate: rateText === "" ? NaN : Number(rateText)
      });
    });
    return {
      planName: els.planName.value.trim(),
      quota: els.quota.value.trim() === "" ? NaN : Number(els.quota.value.trim()),
      accelerator:
        els.accelerator.value.trim() === "" ? NaN : Number(els.accelerator.value.trim()),
      tiers: tiers
    };
  }

  // --- output ---------------------------------------------------------------

  function showProblems(problems) {
    els.results.hidden = true;
    els.problemList.innerHTML = "";
    problems.forEach(function (message) {
      var li = document.createElement("li");
      li.textContent = message;
      els.problemList.appendChild(li);
    });
    els.problems.hidden = false;
  }

  function showResults(plan, breakdown) {
    els.problems.hidden = true;
    els.resultRows.innerHTML = "";

    breakdown.rows.forEach(function (row) {
      var tr = document.createElement("tr");
      if (row.accelerated) {
        tr.className = "accelerated";
      }

      var band =
        CommissionLogic.formatCents(row.fromCents) +
        " to " +
        CommissionLogic.formatCents(row.toCents);

      var aboveText = "0";
      if (row.abovePortionCents > 0) {
        aboveText =
          CommissionLogic.formatCents(row.aboveCommissionCents) +
          " (" +
          CommissionLogic.formatCents(row.abovePortionCents) +
          " at " +
          CommissionLogic.formatBasisPoints(row.rateBp) +
          " x " +
          CommissionLogic.formatAccelerator(breakdown.accelMilli) +
          ")";
      }

      var belowText =
        CommissionLogic.formatCents(row.belowCommissionCents) +
        " (" +
        CommissionLogic.formatCents(row.belowPortionCents) +
        " at " +
        CommissionLogic.formatBasisPoints(row.rateBp) +
        ")";

      appendCell(tr, row.label);
      appendCell(tr, band);
      appendCell(tr, CommissionLogic.formatCents(row.bandRevenueCents));
      appendCell(tr, belowText);
      appendCell(tr, aboveText);
      appendCell(tr, CommissionLogic.formatCents(row.tierTotalCents), "amount");
      els.resultRows.appendChild(tr);
    });

    els.resultTotal.textContent = CommissionLogic.formatCents(breakdown.totalCents);
    els.resultSummary.textContent =
      "Revenue " +
      CommissionLogic.formatCents(breakdown.revenueCents) +
      " against quota " +
      CommissionLogic.formatCents(breakdown.quotaCents) +
      ", accelerator " +
      CommissionLogic.formatAccelerator(breakdown.accelMilli) +
      " on revenue above quota.";
    els.results.hidden = false;
  }

  function appendCell(tr, text, className) {
    var td = document.createElement("td");
    td.textContent = text;
    if (className) {
      td.className = className;
    }
    tr.appendChild(td);
  }

  // --- events ---------------------------------------------------------------

  function calculate() {
    var plan = readPlanFromForm();
    var problems = CommissionLogic.validateRevenue(els.revenue.value).concat(
      CommissionLogic.validatePlan(plan)
    );
    if (problems.length > 0) {
      showProblems(problems);
      return;
    }
    showResults(plan, CommissionLogic.computePayout(plan, els.revenue.value));
  }

  function handlePlanFile(event) {
    var file = event.target.files && event.target.files[0];
    if (!file) {
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      var parsed = CommissionLogic.parsePlanJson(String(reader.result));
      if (!parsed.ok) {
        showProblems([parsed.error]);
        return;
      }
      loadPlanIntoForm(parsed.plan);
    };
    reader.onerror = function () {
      showProblems(["Could not read the selected file."]);
    };
    reader.readAsText(file);
    // Allow re-selecting the same file later.
    event.target.value = "";
  }

  els.calculate.addEventListener("click", calculate);
  els.addTier.addEventListener("click", function () {
    addTierRow();
  });
  els.loadSample.addEventListener("click", function () {
    loadPlanIntoForm(DEFAULT_PLAN);
  });
  els.planFile.addEventListener("change", handlePlanFile);

  // Start with the sample plan loaded so the page is usable immediately.
  loadPlanIntoForm(DEFAULT_PLAN);
})();
