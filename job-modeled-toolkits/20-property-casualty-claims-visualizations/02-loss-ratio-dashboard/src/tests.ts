/*
 * Test harness for the loss-ratio logic. Loads lossratio.js, runs assertions, and
 * prints PASS or FAIL on the page. Open tests.html to see it run.
 *
 * The headline case is the worked example in spec.md: Auto 2022 carries CAD
 * 17,000.00 of incurred losses against CAD 25,000.00 of earned premium, a loss
 * ratio of 68.0 percent. Across the whole book incurred is CAD 119,500.00 and
 * premium is CAD 176,000.00, a 67.9 percent loss ratio.
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

// The clean-claims sample, the exact output of the Claims Aging and Status Funnel,
// inline so the tests do not depend on a file load.
const SAMPLE_CLEAN = [
  "claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,incurred,earned_premium,is_latest,age_days,age_bucket,days_to_close",
  "A-2201,Auto,2022,2022-03-10,2022-12-31,12,open,,8000.00,4000.00,12000.00,25000.00,N,1027,180+,",
  "A-2201,Auto,2022,2022-03-10,2023-12-31,24,open,,11000.00,1000.00,12000.00,25000.00,N,1027,180+,",
  "A-2201,Auto,2022,2022-03-10,2024-12-31,36,closed,2024-06-15,12000.00,0.00,12000.00,25000.00,Y,1027,180+,828",
  "A-2202,Auto,2022,2022-08-01,2022-12-31,12,open,,2000.00,3000.00,5000.00,25000.00,N,883,180+,",
  "A-2202,Auto,2022,2022-08-01,2023-12-31,24,open,,4500.00,500.00,5000.00,25000.00,N,883,180+,",
  "A-2202,Auto,2022,2022-08-01,2024-12-31,36,closed,2024-02-20,5000.00,0.00,5000.00,25000.00,Y,883,180+,568",
  "A-2301,Auto,2023,2023-05-12,2023-12-31,12,open,,3000.00,7000.00,10000.00,30000.00,N,599,180+,",
  "A-2301,Auto,2023,2023-05-12,2024-12-31,24,open,,6000.00,5000.00,11000.00,30000.00,Y,599,180+,",
  "A-2302,Auto,2023,2023-11-30,2023-12-31,12,open,,1000.00,4000.00,5000.00,30000.00,N,397,180+,",
  "A-2302,Auto,2023,2023-11-30,2024-12-31,24,pending,,2500.00,3500.00,6000.00,30000.00,Y,397,180+,",
  "A-2401,Auto,2024,2024-09-15,2024-12-31,12,open,,1500.00,6500.00,8000.00,18000.00,Y,107,91-180,",
  "A-2402,Auto,2024,2024-12-01,2024-12-31,12,open,,500.00,2000.00,2500.00,18000.00,Y,30,0-30,",
  "A-2403,Auto,2024,2024-10-02,2024-12-31,12,pending,,0.00,3000.00,3000.00,18000.00,Y,90,61-90,",
  "P-2201,Property,2022,2022-02-15,2022-12-31,12,open,,20000.00,10000.00,30000.00,40000.00,N,1050,180+,",
  "P-2201,Property,2022,2022-02-15,2023-12-31,24,open,,28000.00,2000.00,30000.00,40000.00,N,1050,180+,",
  "P-2201,Property,2022,2022-02-15,2024-12-31,36,closed,2024-09-10,30000.00,0.00,30000.00,40000.00,Y,1050,180+,938",
  "P-2301,Property,2023,2023-07-20,2023-12-31,12,open,,5000.00,15000.00,20000.00,35000.00,N,530,180+,",
  "P-2301,Property,2023,2023-07-20,2024-12-31,24,open,,12000.00,10000.00,22000.00,35000.00,Y,530,180+,",
  "P-2401,Property,2024,2024-08-05,2024-12-31,12,open,,4000.00,16000.00,20000.00,28000.00,Y,148,91-180,",
].join("\n");

function sampleGrid(): LossRatioGrid {
  return computeLossRatios(parseCleanCsv(SAMPLE_CLEAN));
}

function cell(line: string, period: string): Cell {
  const c = sampleGrid().cells.get(`${line}|${period}`);
  if (!c) {
    throw new Error(`no cell for ${line} ${period}`);
  }
  return c;
}

test("lines and accident years come through sorted", () => {
  const g = sampleGrid();
  assert(g.lines.join(",") === "Auto,Property", `lines were ${g.lines.join(",")}`);
  assert(g.periods.join(",") === "2022,2023,2024", `periods were ${g.periods.join(",")}`);
});

test("only the latest valuation of each claim counts", () => {
  // Auto 2022 has two claims, each with three valuation rows. Incurred must use
  // the latest row of each (12,000.00 and 5,000.00), not every row.
  assert(cell("Auto", "2022").incurredCents === 1700000, `Auto 2022 incurred was ${cell("Auto", "2022").incurredCents}`);
});

test("worked example: Auto 2022 incurred is 17,000.00", () => {
  assert(cell("Auto", "2022").incurredCents === 1700000, "incurred should be 1700000 cents");
});

test("worked example: Auto 2022 premium is 25,000.00, taken once", () => {
  assert(cell("Auto", "2022").premiumCents === 2500000, "premium should be 2500000 cents, not summed over claims");
});

test("worked example: Auto 2022 loss ratio is 68.0%", () => {
  assert(formatRatio(cell("Auto", "2022").ratio) === "68.0%", `ratio was ${formatRatio(cell("Auto", "2022").ratio)}`);
});

test("Auto 2024 loss ratio is 75.0%", () => {
  assert(formatRatio(cell("Auto", "2024").ratio) === "75.0%", `ratio was ${formatRatio(cell("Auto", "2024").ratio)}`);
});

test("Property 2022 loss ratio is 75.0%", () => {
  assert(formatRatio(cell("Property", "2022").ratio) === "75.0%", `ratio was ${formatRatio(cell("Property", "2022").ratio)}`);
});

test("per-line total for Auto is 47,500.00 over 73,000.00 premium", () => {
  const t = sampleGrid().lineTotals.get("Auto") as Cell;
  assert(t.incurredCents === 4750000, `Auto incurred ${t.incurredCents}`);
  assert(t.premiumCents === 7300000, `Auto premium ${t.premiumCents}`);
  assert(formatRatio(t.ratio) === "65.1%", `Auto ratio ${formatRatio(t.ratio)}`);
});

test("per-year total for 2023 is 60.0%", () => {
  const t = sampleGrid().periodTotals.get("2023") as Cell;
  assert(t.incurredCents === 3900000, `2023 incurred ${t.incurredCents}`);
  assert(t.premiumCents === 6500000, `2023 premium ${t.premiumCents}`);
  assert(formatRatio(t.ratio) === "60.0%", `2023 ratio ${formatRatio(t.ratio)}`);
});

test("the whole book is 119,500.00 over 176,000.00, a 67.9% loss ratio", () => {
  const o = sampleGrid().overall;
  assert(o.incurredCents === 11950000, `overall incurred ${o.incurredCents}`);
  assert(o.premiumCents === 17600000, `overall premium ${o.premiumCents}`);
  assert(formatRatio(o.ratio) === "67.9%", `overall ratio ${formatRatio(o.ratio)}`);
});

test("incurred ties back to the funnel total at the latest valuation", () => {
  // The Claims Aging and Status Funnel reports 119,500.00 incurred at latest. The
  // dashboard must reach the same figure from the same file.
  assert(sampleGrid().overall.incurredCents === 11950000, "should match the funnel's 119,500.00");
});

test("parser rejects a register that was not run through the funnel", () => {
  let message = "";
  try {
    parseCleanCsv("claim_id,line_of_business,accident_period\nA,Auto,2024");
  } catch (err) {
    message = err instanceof Error ? err.message : "";
  }
  assert(message.includes("clean-claims.csv exported"), "bad header should point at the funnel export");
});

test("parser rejects a bad is_latest flag", () => {
  let message = "";
  const bad = SAMPLE_CLEAN.replace(",Y,107,91-180,", ",maybe,107,91-180,");
  try {
    parseCleanCsv(bad);
  } catch (err) {
    message = err instanceof Error ? err.message : "";
  }
  assert(message.includes("is_latest"), "bad is_latest should be named");
});

test("parser rejects inconsistent premium within a line and year", () => {
  let message = "";
  const bad = SAMPLE_CLEAN.replace(
    "A-2402,Auto,2024,2024-12-01,2024-12-31,12,open,,500.00,2000.00,2500.00,18000.00,Y,30,0-30,",
    "A-2402,Auto,2024,2024-12-01,2024-12-31,12,open,,500.00,2000.00,2500.00,19000.00,Y,30,0-30,",
  );
  try {
    parseCleanCsv(bad);
  } catch (err) {
    message = err instanceof Error ? err.message : "";
  }
  assert(message.includes("earned_premium"), "inconsistent premium should be named");
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
