/*
 * Test harness for the liquidity-forecast logic. Loads forecast.js, runs
 * assertions, and prints PASS or FAIL on the page. Open tests.html to see it run.
 *
 * The headline case is the worked example in spec.md, the one that ties the three
 * tools together. Opening cash is 648000.50, the sum of the closing balances the
 * Cash Position Dashboard exports. Week 1 debt of 76750.00 and week 13 debt of
 * 75000.00 come from the Maturity Ladder. Against a 100000.00 buffer the forecast
 * breaches in weeks 6 and 7, with the trough at 41250.50 in week 7.
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

// The closing balances the Cash Position Dashboard exports for the sample day.
const CLOSING_BALANCES = [
  "account,closing_balance",
  "CAD-OPS,163500.50",
  "CAD-PAYROLL,1500.00",
  "CAD-RESERVE,500000.00",
  "CAD-TAX,-17000.00",
].join("\n");

// The weekly debt totals the Maturity Ladder exports for the sample obligations.
const MATURITIES = [
  "week,debt_due",
  "1,76750.00",
  "2,12000.00",
  "3,8500.00",
  "4,9000.00",
  "5,0.00",
  "6,0.00",
  "7,0.00",
  "8,0.00",
  "9,0.00",
  "10,0.00",
  "11,0.00",
  "12,0.00",
  "13,75000.00",
].join("\n");

const OPERATING = [
  "week,label,operating_inflows,operating_outflows",
  "1,Wk of Jun 15,90000.00,70000.00",
  "2,Wk of Jun 22,85000.00,163000.00",
  "3,Wk of Jun 29,120000.00,211500.00",
  "4,Wk of Jul 06,60000.00,171000.00",
  "5,Wk of Jul 13,95000.00,205000.00",
  "6,Wk of Jul 20,100000.00,190000.00",
  "7,Wk of Jul 27,70000.00,110000.00",
  "8,Wk of Aug 03,150000.00,90000.00",
  "9,Wk of Aug 10,130000.00,90000.00",
  "10,Wk of Aug 17,130000.00,100000.00",
  "11,Wk of Aug 24,90000.00,65000.00",
  "12,Wk of Aug 31,90000.00,70000.00",
  "13,Wk of Sep 07,100000.00,95000.00",
].join("\n");

function runSample(): WeekResult[] {
  const opening = sumClosingBalancesCsv(CLOSING_BALANCES);
  const flows = parseOperatingCsv(OPERATING);
  const debt = parseMaturitiesCsv(MATURITIES);
  return runForecast(flows, debt, { openingCashCents: opening, minimumBufferCents: 10000000 });
}

test("opening cash is the sum of the dashboard's closing balances", () => {
  assert(sumClosingBalancesCsv(CLOSING_BALANCES) === 64800050, "sum is 648000.50");
});

test("a negative closing balance lowers the opening cash", () => {
  const total = sumClosingBalancesCsv("account,closing_balance\nCAD-A,100.00\nCAD-B,-25.50");
  assert(total === 7450, "100.00 - 25.50 is 74.50");
});

test("operating CSV requires all 13 weeks", () => {
  let message = "";
  try {
    parseOperatingCsv("week,label,operating_inflows,operating_outflows\n1,a,1.00,1.00");
  } catch (err) {
    message = err instanceof Error ? err.message : "";
  }
  assert(message.includes("missing week 2"), "a gap should be named");
});

test("operating CSV rejects a duplicate week", () => {
  let message = "";
  try {
    parseOperatingCsv("week,label,operating_inflows,operating_outflows\n1,a,1.00,1.00\n1,b,2.00,2.00");
  } catch (err) {
    message = err instanceof Error ? err.message : "";
  }
  assert(message.includes("appears more than once"), "a duplicate week should be named");
});

test("operating CSV rejects a bad header", () => {
  let threw = false;
  try {
    parseOperatingCsv("wk,note,in,out\n1,a,1.00,1.00");
  } catch {
    threw = true;
  }
  assert(threw, "bad header should throw");
});

test("worked example week 1: debt loads in and closing is 591250.50", () => {
  const results = runSample();
  const w1 = results[0];
  assert(w1.openingCents === 64800050, "opening 648000.50");
  assert(w1.debtDueCents === 7675000, "debt due 76750.00 from the ladder");
  assert(w1.totalOutflowCents === 14675000, "total outflows 146750.00");
  assert(w1.netCents === -5675000, "net -56750.00");
  assert(w1.closingCents === 59125050, "closing 591250.50");
  assert(!w1.breach, "week 1 stays above the buffer");
});

test("worked example: the trough is week 7 at 41250.50", () => {
  const results = runSample();
  const w7 = results[6];
  assert(w7.openingCents === 8125050, "week 7 opens at 81250.50 (week 6 close)");
  assert(w7.netCents === -4000000, "net -40000.00");
  assert(w7.closingCents === 4125050, "closing 41250.50");
  assert(w7.breach, "week 7 is below the 100000.00 buffer");
  assert(w7.headroomCents === -5874950, "shortfall 58749.50 below the buffer");
});

test("worked example: week 13 carries the 75000.00 maturity", () => {
  const results = runSample();
  const w13 = results[12];
  assert(w13.debtDueCents === 7500000, "debt due 75000.00 from the ladder");
  assert(w13.totalOutflowCents === 17000000, "total outflows 170000.00");
  assert(w13.closingCents === 14625050, "ending cash 146250.50");
});

test("summary counts the two breaches and finds the trough", () => {
  const summary = summarize(runSample());
  assert(summary.breachCount === 2, "weeks 6 and 7 breach");
  assert(summary.firstBreachWeek === 6, "first breach is week 6");
  assert(summary.lowestWeek === 7 && summary.lowestClosingCents === 4125050, "trough week 7 at 41250.50");
  assert(summary.endingCashCents === 14625050, "ending cash 146250.50");
});

test("a missing maturities file leaves debt at zero", () => {
  const flows = parseOperatingCsv(OPERATING);
  const results = runForecast(flows, new Map(), { openingCashCents: 64800050, minimumBufferCents: 10000000 });
  assert(results[0].debtDueCents === 0, "no debt without the ladder file");
  assert(results[0].closingCents === 66800050, "week 1 closes higher with no debt: 668000.50");
});

test("forecast CSV writes a row per week with the breach flag", () => {
  const csv = toForecastCsv(runSample());
  const rows = csv.split("\n");
  assert(rows[0].startsWith("week,label,opening,inflows"), "header");
  assert(rows[1] === "1,Wk of Jun 15,648000.50,90000.00,70000.00,76750.00,146750.00,-56750.00,591250.50,ok", "week 1 row");
  assert(rows[7].endsWith(",41250.50,breach"), "week 7 row is flagged a breach");
  assert(rows.length === 14, "header plus 13 weeks");
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
