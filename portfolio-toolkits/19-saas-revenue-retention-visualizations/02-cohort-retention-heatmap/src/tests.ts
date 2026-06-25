/*
 * Test harness for the cohort retention logic. Loads cohort.js, runs assertions,
 * and prints PASS or FAIL on the page. Open tests.html to see it run.
 *
 * The headline case is the worked example in spec.md: the January 2025 cohort
 * starts at 1,050.00 across three customers and holds 1,300.00 across two by its
 * fourth month, which is 123.81% revenue retention and 66.67% logo retention.
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

const SAMPLE_LEDGER = [
  "customer_id,plan,signup_month,month,mrr",
  "C001,Pro,2025-01,2025-01,200.00",
  "C001,Pro,2025-01,2025-02,200.00",
  "C001,Pro,2025-01,2025-03,200.00",
  "C001,Pro,2025-01,2025-04,300.00",
  "C001,Pro,2025-01,2025-05,300.00",
  "C002,Basic,2025-01,2025-01,50.00",
  "C002,Basic,2025-01,2025-02,50.00",
  "C002,Basic,2025-01,2025-03,50.00",
  "C003,Enterprise,2025-01,2025-01,800.00",
  "C003,Enterprise,2025-01,2025-02,800.00",
  "C003,Enterprise,2025-01,2025-03,1000.00",
  "C003,Enterprise,2025-01,2025-04,1000.00",
  "C003,Enterprise,2025-01,2025-05,1000.00",
  "C004,Pro,2025-02,2025-02,200.00",
  "C004,Pro,2025-02,2025-03,200.00",
  "C004,Pro,2025-02,2025-04,150.00",
  "C004,Pro,2025-02,2025-05,150.00",
  "C005,Basic,2025-02,2025-02,50.00",
  "C005,Basic,2025-02,2025-03,50.00",
  "C005,Basic,2025-02,2025-04,50.00",
  "C005,Basic,2025-02,2025-05,50.00",
  "C006,Enterprise,2025-03,2025-03,800.00",
  "C006,Enterprise,2025-03,2025-04,800.00",
  "C006,Enterprise,2025-03,2025-05,800.00",
  "C007,Pro,2025-03,2025-03,200.00",
  "C007,Pro,2025-03,2025-04,200.00",
  "C007,Pro,2025-03,2025-05,200.00",
  "C008,Basic,2025-04,2025-04,50.00",
  "C008,Basic,2025-04,2025-05,50.00",
  "C009,Pro,2025-04,2025-04,200.00",
  "C009,Pro,2025-04,2025-05,200.00",
  "C010,Basic,2025-05,2025-05,50.00",
].join("\n");

function cohort(month: string): CohortSeries {
  const series = computeCohorts(parseLedgerCsv(SAMPLE_LEDGER));
  const found = series.find((s) => s.cohort === month);
  if (!found) {
    throw new Error(`cohort ${month} missing`);
  }
  return found;
}

test("five cohorts, January through May", () => {
  const series = computeCohorts(parseLedgerCsv(SAMPLE_LEDGER));
  assert(series.length === 5, "five signup cohorts");
  assert(series[0].cohort === "2025-01" && series[4].cohort === "2025-05", "ordered ascending");
});

test("the January cohort starts at 1,050.00 across three customers", () => {
  const jan = cohort("2025-01");
  assert(jan.startCents === 105000, "start should be 105000 cents");
  assert(jan.cohortSize === 3, "three customers");
});

test("every cohort retains 100% at offset 0", () => {
  for (const s of computeCohorts(parseLedgerCsv(SAMPLE_LEDGER))) {
    assert(s.cells[0].revenuePct === 100, `${s.cohort} offset 0 revenue`);
    assert(s.cells[0].logoPct === 100, `${s.cohort} offset 0 logos`);
  }
});

test("worked example: January cohort offset 3 retains 1,300.00", () => {
  const cell = cohort("2025-01").cells[3];
  assert(cell.retainedCents === 130000, "retained should be 130000 cents");
  assert(cell.revenuePct === 123.81, `revenue retention should be 123.81, got ${cell.revenuePct}`);
});

test("worked example: January cohort offset 3 holds two of three logos", () => {
  const cell = cohort("2025-01").cells[3];
  assert(cell.activeLogos === 2, "two active logos");
  assert(cell.logoPct === 66.67, `logo retention should be 66.67, got ${cell.logoPct}`);
});

test("a contraction shows as a revenue dip: February cohort offset 2 is 80%", () => {
  const cell = cohort("2025-02").cells[2];
  assert(cell.retainedCents === 20000, "retained should be 20000 cents");
  assert(cell.revenuePct === 80, `revenue retention should be 80, got ${cell.revenuePct}`);
  assert(cell.logoPct === 100, "both logos still active");
});

test("cells past the end of the ledger are blank", () => {
  const may = cohort("2025-05");
  assert(may.cells[0].hasData === true, "offset 0 has data");
  assert(may.cells[1].hasData === false, "offset 1 is past the ledger");
});

test("parser rejects a bad header", () => {
  let threw = false;
  try {
    parseLedgerCsv("id,plan,start,month,amount\nC001,Pro,2025-01,2025-01,50.00");
  } catch {
    threw = true;
  }
  assert(threw, "bad header should throw");
});

test("parser rejects an unknown plan", () => {
  let message = "";
  try {
    parseLedgerCsv("customer_id,plan,signup_month,month,mrr\nC001,Gold,2025-01,2025-01,50.00");
  } catch (err) {
    message = err instanceof Error ? err.message : "";
  }
  assert(message.includes("plan"), "unknown plan should be named");
});

test("parser rejects a duplicate customer-month", () => {
  let message = "";
  try {
    parseLedgerCsv("customer_id,plan,signup_month,month,mrr\nC001,Pro,2025-01,2025-01,50.00\nC001,Pro,2025-01,2025-01,60.00");
  } catch (err) {
    message = err instanceof Error ? err.message : "";
  }
  assert(message.includes("already has a row"), "duplicate should be named");
});

test("parser rejects a non-positive MRR", () => {
  let threw = false;
  try {
    parseLedgerCsv("customer_id,plan,signup_month,month,mrr\nC001,Pro,2025-01,2025-01,0");
  } catch {
    threw = true;
  }
  assert(threw, "zero MRR should throw");
});

test("cohort CSV round-trips the January row", () => {
  const csv = toCohortCsv(computeCohorts(parseLedgerCsv(SAMPLE_LEDGER)));
  assert(csv.split("\n")[0] === "cohort,start_mrr,cohort_size,month_0,month_1,month_2,month_3,month_4", "header");
  assert(csv.includes("2025-01,1050.00,3,100.00,100.00,119.05,123.81,123.81"), "January row matches the worked example");
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
