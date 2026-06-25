/*
 * Test harness for the churn, retention, and renewal logic. Loads retention.js,
 * runs assertions, and prints PASS or FAIL on the page. Open tests.html to run.
 *
 * The headline case is the worked example in spec.md and ties this tool back to
 * the MRR Movement Waterfall: reading the waterfall's April 2025 row (opening
 * 2,500.00, expansion 100.00, contraction 50.00, churn 50.00) gives a 2.00%
 * churn rate, 96.00% gross revenue retention, and 100.00% net revenue retention.
 */

interface TestCase {
  name: string;
  run: () => void;
}

const tests: TestCase[] = [];
function test(name: string, run: () => void): void {
  tests.push({ name, run });
}

function assert(condition: boolean, detail: string): void {
  if (!condition) {
    throw new Error(detail);
  }
}

// The exact movement table the waterfall exports from the sample ledger.
const SAMPLE_MOVEMENT = [
  "month,opening_mrr,new_mrr,expansion_mrr,contraction_mrr,churned_mrr,closing_mrr",
  "2025-01,0.00,1050.00,0.00,0.00,0.00,1050.00",
  "2025-02,1050.00,250.00,0.00,0.00,0.00,1300.00",
  "2025-03,1300.00,1000.00,200.00,0.00,0.00,2500.00",
  "2025-04,2500.00,250.00,100.00,50.00,50.00,2750.00",
  "2025-05,2750.00,50.00,0.00,0.00,0.00,2800.00",
].join("\n");

const SAMPLE_RENEWALS = [
  "customer_id,mrr,renewal_month,term_months",
  "C001,300.00,2025-06,12",
  "C003,1000.00,2025-07,12",
  "C004,150.00,2025-06,12",
  "C005,50.00,2025-08,12",
  "C006,800.00,2026-01,12",
  "C007,200.00,2025-06,1",
  "C008,50.00,2025-10,1",
  "C009,200.00,2025-09,1",
  "C010,50.00,2025-11,1",
].join("\n");

function retentionFor(month: string): RetentionRow {
  const rows = computeRetention(parseMovementCsv(SAMPLE_MOVEMENT));
  const found = rows.find((r) => r.month === month);
  if (!found) {
    throw new Error(`retention row ${month} missing`);
  }
  return found;
}

test("worked example: April churn rate is 2.00%", () => {
  assert(retentionFor("2025-04").churnRatePct === 2, `got ${retentionFor("2025-04").churnRatePct}`);
});

test("worked example: April gross revenue retention is 96.00%", () => {
  assert(retentionFor("2025-04").grrPct === 96, `got ${retentionFor("2025-04").grrPct}`);
});

test("worked example: April net revenue retention is 100.00%", () => {
  assert(retentionFor("2025-04").nrrPct === 100, `got ${retentionFor("2025-04").nrrPct}`);
});

test("expansion lifts NRR above GRR: March NRR is 115.38%", () => {
  const mar = retentionFor("2025-03");
  assert(mar.grrPct === 100, `March GRR ${mar.grrPct}`);
  assert(mar.nrrPct === 115.38, `March NRR ${mar.nrrPct}`);
});

test("a month with no opening base has undefined rates", () => {
  const jan = retentionFor("2025-01");
  assert(jan.hasBase === false, "January has no base");
});

test("a clean month with no losses retains 100% gross", () => {
  const may = retentionFor("2025-05");
  assert(may.churnRatePct === 0, "no churn in May");
  assert(may.grrPct === 100, "May GRR is 100");
});

test("movement parser rejects a file that does not reconcile", () => {
  let message = "";
  try {
    parseMovementCsv("month,opening_mrr,new_mrr,expansion_mrr,contraction_mrr,churned_mrr,closing_mrr\n2025-04,2500.00,250.00,100.00,50.00,50.00,9999.00");
  } catch (err) {
    message = err instanceof Error ? err.message : "";
  }
  assert(message.includes("does not reconcile"), "non-reconciling row should be named");
});

test("movement parser rejects a bad header", () => {
  let threw = false;
  try {
    parseMovementCsv("month,open,new,exp,contr,churn,close\n2025-04,2500.00,250.00,100.00,50.00,50.00,2750.00");
  } catch {
    threw = true;
  }
  assert(threw, "bad header should throw");
});

test("upcoming renewals group by month within the horizon", () => {
  const buckets = upcomingRenewals(parseRenewalsCsv(SAMPLE_RENEWALS), "2025-05", 3);
  assert(buckets.length === 3, `three months in window, got ${buckets.length}`);
  assert(buckets[0].month === "2025-06" && buckets[0].count === 3 && buckets[0].valueCents === 65000, "June: 3 renewals, 650.00");
  assert(buckets[1].month === "2025-07" && buckets[1].valueCents === 100000, "July: 1,000.00");
  assert(buckets[2].month === "2025-08" && buckets[2].valueCents === 5000, "August: 50.00");
});

test("renewals outside the horizon are left out", () => {
  const buckets = upcomingRenewals(parseRenewalsCsv(SAMPLE_RENEWALS), "2025-05", 3);
  const months = buckets.map((b) => b.month);
  assert(!months.includes("2025-09"), "September is past a 3-month horizon");
  assert(!months.includes("2026-01"), "next January is well past the horizon");
});

test("renewals parser rejects a non-positive term", () => {
  let message = "";
  try {
    parseRenewalsCsv("customer_id,mrr,renewal_month,term_months\nC001,300.00,2025-06,0");
  } catch (err) {
    message = err instanceof Error ? err.message : "";
  }
  assert(message.includes("term_months"), "zero term should be named");
});

test("renewals parser rejects a duplicate customer", () => {
  let message = "";
  try {
    parseRenewalsCsv("customer_id,mrr,renewal_month,term_months\nC001,300.00,2025-06,12\nC001,200.00,2025-07,12");
  } catch (err) {
    message = err instanceof Error ? err.message : "";
  }
  assert(message.includes("already has a renewal"), "duplicate should be named");
});

function runTests(): void {
  const root = document.getElementById("results");
  if (!root) {
    return;
  }
  let passed = 0;
  for (const t of tests) {
    const row = document.createElement("div");
    row.className = "test-row";
    try {
      t.run();
      row.classList.add("pass");
      row.textContent = `PASS  ${t.name}`;
      passed += 1;
    } catch (err) {
      row.classList.add("fail");
      row.textContent = `FAIL  ${t.name}  ->  ${err instanceof Error ? err.message : String(err)}`;
    }
    root.appendChild(row);
  }
  const header = document.getElementById("summary");
  if (header) {
    const allPass = passed === tests.length;
    header.textContent = `${passed} / ${tests.length} passed`;
    header.className = allPass ? "summary pass" : "summary fail";
  }
}

document.addEventListener("DOMContentLoaded", runTests);
