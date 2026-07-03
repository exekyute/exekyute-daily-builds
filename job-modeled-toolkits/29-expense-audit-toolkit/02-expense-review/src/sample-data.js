/* Synthetic sample expenses and the policy, for the review app.
 *
 * Loaded on first open so the app shows a queue without an import, and used by the
 * tests. The expenses match the engine's expenses.csv in 01 row for row, and the
 * policy matches policy.csv, so the app and the Python auditor flag the same lines.
 * Seeded to touch every flag: a clean mileage claim, a mileage mismatch, an over-cap
 * meal, a missing receipt, and a duplicate pair.
 */
(function (global) {
  "use strict";

  var POLICY = {
    mileage_rate: "0.70",
    receipt_threshold: "25.00",
    caps: { Meals: "75.00", Lodging: "250.00", Supplies: "200.00", Transport: "150.00" },
  };

  var SAMPLE_EXPENSES = [
    { expense_id: "E-01", date: "2026-06-02", employee: "J. Tremblay", category: "Mileage", amount: "175.00", km: "250", receipt: "no" },
    { expense_id: "E-02", date: "2026-06-03", employee: "J. Tremblay", category: "Mileage", amount: "220.00", km: "300", receipt: "no" },
    { expense_id: "E-03", date: "2026-06-04", employee: "A. Singh", category: "Meals", amount: "95.00", km: "", receipt: "yes" },
    { expense_id: "E-04", date: "2026-06-05", employee: "A. Singh", category: "Supplies", amount: "40.00", km: "", receipt: "no" },
    { expense_id: "E-05", date: "2026-06-06", employee: "M. Chen", category: "Lodging", amount: "240.00", km: "", receipt: "yes" },
    { expense_id: "E-06", date: "2026-06-07", employee: "M. Chen", category: "Meals", amount: "60.00", km: "", receipt: "yes" },
    { expense_id: "E-07", date: "2026-06-07", employee: "M. Chen", category: "Meals", amount: "60.00", km: "", receipt: "yes" }
  ];

  var payload = { policy: POLICY, expenses: SAMPLE_EXPENSES };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = payload;
  } else {
    global.EXPENSE_SAMPLE = payload;
  }
})(typeof window !== "undefined" ? window : globalThis);
