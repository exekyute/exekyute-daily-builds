/* Synthetic SOW timeline, generated from the engine output in 01.
 * Embedded so the view renders by double-clicking index.html. The Import
 * button can load a fresh timeline.csv. These match the engine to the cent.
 */
(function (global) {
  "use strict";
  var TOTAL_BUDGET = 80000.0;
  var SAMPLE_TIMELINE = [
  {
    "week": 1.0,
    "cost_to_date": 21000.0,
    "earned_value": 20000.0,
    "percent_complete": 0.25,
    "percent_spent": 0.2625,
    "cpi": 0.9524,
    "eac": 84000.0,
    "vac": -4000.0,
    "holdback_accrued": 2000.0,
    "holdback_released": 0.0,
    "status": "At risk"
  },
  {
    "week": 2.0,
    "cost_to_date": 37000.0,
    "earned_value": 35000.0,
    "percent_complete": 0.4375,
    "percent_spent": 0.4625,
    "cpi": 0.9459,
    "eac": 84571.43,
    "vac": -4571.43,
    "holdback_accrued": 3500.0,
    "holdback_released": 0.0,
    "status": "Over budget"
  },
  {
    "week": 3.0,
    "cost_to_date": 52000.0,
    "earned_value": 50000.0,
    "percent_complete": 0.625,
    "percent_spent": 0.65,
    "cpi": 0.9615,
    "eac": 83200.0,
    "vac": -3200.0,
    "holdback_accrued": 5000.0,
    "holdback_released": 0.0,
    "status": "At risk"
  },
  {
    "week": 4.0,
    "cost_to_date": 70000.0,
    "earned_value": 68000.0,
    "percent_complete": 0.85,
    "percent_spent": 0.875,
    "cpi": 0.9714,
    "eac": 82352.94,
    "vac": -2352.94,
    "holdback_accrued": 6800.0,
    "holdback_released": 0.0,
    "status": "At risk"
  },
  {
    "week": 5.0,
    "cost_to_date": 85000.0,
    "earned_value": 80000.0,
    "percent_complete": 1.0,
    "percent_spent": 1.0625,
    "cpi": 0.9412,
    "eac": 85000.0,
    "vac": -5000.0,
    "holdback_accrued": 8000.0,
    "holdback_released": 8000.0,
    "status": "Over budget"
  }
];
  var SAMPLE_MILESTONES = [
  {
    "milestone_id": "M1",
    "name": "Discovery",
    "budget": 20000.0,
    "actual_cost": 21000.0,
    "variance": -1000.0,
    "percent_spent": 1.05,
    "status": "Over budget"
  },
  {
    "milestone_id": "M2",
    "name": "Design",
    "budget": 15000.0,
    "actual_cost": 16000.0,
    "variance": -1000.0,
    "percent_spent": 1.0667,
    "status": "Over budget"
  },
  {
    "milestone_id": "M3",
    "name": "Build A",
    "budget": 15000.0,
    "actual_cost": 15000.0,
    "variance": 0.0,
    "percent_spent": 1.0,
    "status": "On budget"
  },
  {
    "milestone_id": "M4",
    "name": "Build B",
    "budget": 18000.0,
    "actual_cost": 18000.0,
    "variance": 0.0,
    "percent_spent": 1.0,
    "status": "On budget"
  },
  {
    "milestone_id": "M5",
    "name": "Launch",
    "budget": 12000.0,
    "actual_cost": 15000.0,
    "variance": -3000.0,
    "percent_spent": 1.25,
    "status": "Over budget"
  }
];
  var payload = { totalBudget: TOTAL_BUDGET, timeline: SAMPLE_TIMELINE, milestones: SAMPLE_MILESTONES };
  if (typeof module !== "undefined" && module.exports) { module.exports = payload; }
  else { global.SOW_SAMPLE = payload; }
})(typeof window !== "undefined" ? window : globalThis);
