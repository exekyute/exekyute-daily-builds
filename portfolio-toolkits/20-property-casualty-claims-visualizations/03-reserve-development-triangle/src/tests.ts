/*
 * Test harness for the reserve-development logic. Loads triangle.js, runs
 * assertions, and prints PASS or FAIL on the page. Open tests.html to see it run.
 *
 * The headline case is the worked example in spec.md: for the whole book the
 * 12-to-24 month development factor is 1.6410 and the 24-to-36 month factor is
 * 1.0805, so a claim valued at 12 months develops to ultimate by 1.7731.
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

function whole(): Triangle {
  return buildTriangle(parseCleanCsv(SAMPLE_CLEAN), "All");
}

test("the line filter offers All plus each line", () => {
  assert(linesIn(parseCleanCsv(SAMPLE_CLEAN)).join(",") === "All,Auto,Property", "expected All,Auto,Property");
});

test("accident years and development months come through sorted", () => {
  const t = whole();
  assert(t.periods.join(",") === "2022,2023,2024", `periods ${t.periods.join(",")}`);
  assert(t.devMonths.join(",") === "12,24,36", `dev ${t.devMonths.join(",")}`);
});

test("the triangle sums cumulative paid into the right cells", () => {
  const t = whole();
  assert(t.cells.get("2022|12") === 3000000, "2022 at 12 months is 30,000.00");
  assert(t.cells.get("2022|24") === 4350000, "2022 at 24 months is 43,500.00");
  assert(t.cells.get("2022|36") === 4700000, "2022 at 36 months is 47,000.00");
  assert(t.cells.get("2023|12") === 900000, "2023 at 12 months is 9,000.00");
  assert(t.cells.get("2023|24") === 2050000, "2023 at 24 months is 20,500.00");
  assert(t.cells.get("2024|12") === 600000, "2024 at 12 months is 6,000.00");
});

test("the triangle has no cell where a year is not yet that mature", () => {
  const t = whole();
  assert(t.cells.get("2023|36") === undefined, "2023 has no 36-month cell");
  assert(t.cells.get("2024|24") === undefined, "2024 has no 24-month cell");
});

test("worked example: the 12-to-24 month factor is 1.6410", () => {
  const f = whole().ageToAge.find((a) => a.from === 12 && a.to === 24);
  assert(f !== undefined && f.factor.toFixed(4) === "1.6410", `factor was ${f && f.factor.toFixed(4)}`);
});

test("worked example: the 24-to-36 month factor is 1.0805", () => {
  const f = whole().ageToAge.find((a) => a.from === 24 && a.to === 36);
  assert(f !== undefined && f.factor.toFixed(4) === "1.0805", `factor was ${f && f.factor.toFixed(4)}`);
});

test("worked example: a claim at 12 months develops to ultimate by 1.7731", () => {
  const t = whole();
  assert((t.cdf.get(12) as number).toFixed(4) === "1.7731", `cdf12 was ${(t.cdf.get(12) as number).toFixed(4)}`);
  assert((t.cdf.get(24) as number).toFixed(4) === "1.0805", `cdf24 was ${(t.cdf.get(24) as number).toFixed(4)}`);
  assert(t.cdf.get(36) === 1, "the most mature age develops by 1.0000");
});

test("a fully mature year projects to its own paid with no reserve", () => {
  const p = whole().projections.find((x) => x.period === "2022");
  assert(p !== undefined && p.ultimateCents === 4700000 && p.reserveCents === 0, "2022 is at ultimate already");
});

test("the youngest year carries the largest projected reserve", () => {
  const p = whole().projections.find((x) => x.period === "2024");
  assert(p !== undefined && p.latestDev === 12, "2024 sits at 12 months");
  assert(p !== undefined && p.ultimateCents === 1063837, `2024 ultimate was ${p && p.ultimateCents}`);
  assert(p !== undefined && p.reserveCents === 463837, `2024 reserve was ${p && p.reserveCents}`);
});

test("the 2023 projection lifts 20,500.00 to 22,149.43 ultimate", () => {
  const p = whole().projections.find((x) => x.period === "2023");
  assert(p !== undefined && p.ultimateCents === 2214943, `2023 ultimate was ${p && p.ultimateCents}`);
  assert(p !== undefined && p.reserveCents === 164943, `2023 reserve was ${p && p.reserveCents}`);
});

test("filtering to Auto changes the development factor", () => {
  const auto = buildTriangle(parseCleanCsv(SAMPLE_CLEAN), "Auto");
  const f = auto.ageToAge.find((a) => a.from === 12 && a.to === 24);
  assert(f !== undefined && f.factor.toFixed(4) === "1.7143", `Auto 12-to-24 was ${f && f.factor.toFixed(4)}`);
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

test("parser rejects a non-numeric development month", () => {
  let message = "";
  const bad = SAMPLE_CLEAN.replace(",36,closed,2024-06-15,", ",end,closed,2024-06-15,");
  try {
    parseCleanCsv(bad);
  } catch (err) {
    message = err instanceof Error ? err.message : "";
  }
  assert(message.includes("development_month"), "bad development month should be named");
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
