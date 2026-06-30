/* Synthetic sample subscriptions for the license manager.
 *
 * Loaded on first open so the app shows data without an import, and used by the
 * tests. These match the engine's subscriptions.csv in 01 row for row, so the
 * app and the Python ledger produce the same numbers. Seeded to touch every
 * branch: a clean per-seat plan, an underused auto-renewing one, a flat plan, a
 * fully used plan, an expired one, and a renewal due within the month.
 */
(function (global) {
  "use strict";

  var SAMPLE_SUBSCRIPTIONS = [
    { sub_id: "S-01", vendor: "Atlas CRM", plan: "Team", plan_type: "per_seat", monthly_unit_cost: "12", seats_owned: "50", seats_used: "38", renewal_date: "2026-09-15", auto_renew: "yes" },
    { sub_id: "S-02", vendor: "Beacon Analytics", plan: "Pro", plan_type: "per_seat", monthly_unit_cost: "25", seats_owned: "40", seats_used: "18", renewal_date: "2026-07-20", auto_renew: "yes" },
    { sub_id: "S-03", vendor: "Cirrus Storage", plan: "Business", plan_type: "flat", monthly_unit_cost: "300", seats_owned: "10", seats_used: "10", renewal_date: "2026-12-01", auto_renew: "no" },
    { sub_id: "S-04", vendor: "Delta Security", plan: "Enterprise", plan_type: "per_seat", monthly_unit_cost: "8", seats_owned: "100", seats_used: "100", renewal_date: "2027-01-31", auto_renew: "yes" },
    { sub_id: "S-05", vendor: "Echo Design", plan: "Studio", plan_type: "per_seat", monthly_unit_cost: "15", seats_owned: "25", seats_used: "9", renewal_date: "2026-06-10", auto_renew: "no" },
    { sub_id: "S-06", vendor: "Forge CI", plan: "Growth", plan_type: "per_seat", monthly_unit_cost: "50", seats_owned: "12", seats_used: "11", renewal_date: "2026-07-05", auto_renew: "yes" }
  ];

  if (typeof module !== "undefined" && module.exports) {
    module.exports = SAMPLE_SUBSCRIPTIONS;
  } else {
    global.SAMPLE_SUBSCRIPTIONS = SAMPLE_SUBSCRIPTIONS;
  }
})(typeof window !== "undefined" ? window : globalThis);
