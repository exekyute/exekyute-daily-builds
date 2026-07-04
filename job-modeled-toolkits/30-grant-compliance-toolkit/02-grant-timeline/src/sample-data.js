/* Synthetic grant timeline, generated from the engine output in 01.
 * Embedded so the view renders by double-clicking index.html. The Import
 * button can load a fresh timeline.csv. These match the engine to the cent.
 */
(function (global) {
  "use strict";
  var AWARD_TOTAL = 250000.0;
  var SAMPLE_TIMELINE = [
  {
    "period": 1.0,
    "cumulative_allowable": 16000.0,
    "cumulative_disallowed": 0.0,
    "burn_rate": 16000.0,
    "remaining": 234000.0,
    "projected_total": 192000.0,
    "projected_variance": 58000.0,
    "status": "On track",
    "reports_overdue": 0.0
  },
  {
    "period": 2.0,
    "cumulative_allowable": 46000.0,
    "cumulative_disallowed": 5000.0,
    "burn_rate": 23000.0,
    "remaining": 204000.0,
    "projected_total": 276000.0,
    "projected_variance": -26000.0,
    "status": "Over budget",
    "reports_overdue": 0.0
  },
  {
    "period": 3.0,
    "cumulative_allowable": 76000.0,
    "cumulative_disallowed": 5000.0,
    "burn_rate": 25333.33,
    "remaining": 174000.0,
    "projected_total": 304000.0,
    "projected_variance": -54000.0,
    "status": "Over budget",
    "reports_overdue": 1.0
  },
  {
    "period": 4.0,
    "cumulative_allowable": 100000.0,
    "cumulative_disallowed": 5000.0,
    "burn_rate": 25000.0,
    "remaining": 150000.0,
    "projected_total": 300000.0,
    "projected_variance": -50000.0,
    "status": "Over budget",
    "reports_overdue": 1.0
  }
];
  var SAMPLE_CATEGORIES = [
  {
    "category": "Equipment",
    "budget": 40000.0,
    "spent": 12000.0,
    "remaining": 28000.0,
    "status": "Within budget"
  },
  {
    "category": "Indirect",
    "budget": 40000.0,
    "spent": 3000.0,
    "remaining": 37000.0,
    "status": "Within budget"
  },
  {
    "category": "Salaries",
    "budget": 150000.0,
    "spent": 80000.0,
    "remaining": 70000.0,
    "status": "Within budget"
  },
  {
    "category": "Travel",
    "budget": 20000.0,
    "spent": 5000.0,
    "remaining": 15000.0,
    "status": "Within budget"
  }
];
  var SAMPLE_DEADLINES = [
  {
    "report": "Q1 financial report",
    "due_period": 3.0,
    "submitted": "no",
    "status": "Overdue"
  },
  {
    "report": "Mid-term report",
    "due_period": 6.0,
    "submitted": "no",
    "status": "Upcoming"
  },
  {
    "report": "Final report",
    "due_period": 12.0,
    "submitted": "no",
    "status": "Upcoming"
  }
];
  var payload = { awardTotal: AWARD_TOTAL, timeline: SAMPLE_TIMELINE, categories: SAMPLE_CATEGORIES, deadlines: SAMPLE_DEADLINES };
  if (typeof module !== "undefined" && module.exports) { module.exports = payload; }
  else { global.GRANT_SAMPLE = payload; }
})(typeof window !== "undefined" ? window : globalThis);
