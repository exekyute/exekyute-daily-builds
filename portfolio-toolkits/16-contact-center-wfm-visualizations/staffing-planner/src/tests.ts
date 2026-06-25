/*
 * Test harness for the staffing logic. Loads erlang.js, runs assertions, and
 * prints PASS or FAIL on the page. Open tests.html to see it run.
 *
 * The headline case is the worked example in spec.md: 100 calls in a 30-minute
 * interval at 180s AHT is 10 Erlangs of load. Against an 80%-in-20s target,
 * 13 agents fall short (about 79.56%) and 14 agents clear it (about 88.84%).
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

function assertClose(actual: number, expected: number, tolerance: number, detail: string): void {
  if (Math.abs(actual - expected) > tolerance) {
    throw new Error(`${detail}: expected ${expected}, got ${actual}`);
  }
}

test("traffic intensity is talk-seconds over interval-seconds", () => {
  assertClose(trafficIntensity(100, 180, 1800), 10, 1e-9, "10 Erlangs");
});

test("Erlang C reaches 1 when the centre is unstable", () => {
  assertClose(erlangC(10, 10), 1, 1e-9, "agents equal to load");
  assertClose(erlangC(9, 10), 1, 1e-9, "agents below load");
});

test("worked example: 13 agents fall short of 80/20", () => {
  const sl = serviceLevel(13, 10, 180, 20) * 100;
  assertClose(sl, 79.56, 0.05, "SL at 13 agents");
  assert(sl < 80, "13 agents should be under the 80% target");
});

test("worked example: 14 agents clear 80/20", () => {
  const sl = serviceLevel(14, 10, 180, 20) * 100;
  assertClose(sl, 88.835, 0.01, "SL at 14 agents");
  assert(sl >= 80, "14 agents should meet the 80% target");
});

test("requiredAgents picks the smallest count that meets target", () => {
  assert(requiredAgents(10, 180, 20, 0.8) === 14, "should need 14 agents");
});

test("occupancy at the required staffing is load over agents", () => {
  const result = planInterval({ interval: "08:00", callsOffered: 100, ahtSeconds: 180 }, {
    intervalMinutes: 30,
    targetSlPct: 80,
    targetAnswerSeconds: 20,
    shrinkagePct: 30,
  });
  assert(result.requiredAgents === 14, "14 required");
  assertClose(result.occupancyPct, 71.43, 0.01, "occupancy 10/14");
  assertClose(result.projectedSlPct, 88.84, 0.001, "projected SL");
});

test("shrinkage rounds the roster up: 14 at 30% becomes 20", () => {
  assert(scheduledWithShrinkage(14, 30) === 20, "14 / 0.7 rounds up to 20");
});

test("a zero-volume interval needs no agents and reports full SL", () => {
  const result = planInterval({ interval: "23:30", callsOffered: 0, ahtSeconds: 180 }, {
    intervalMinutes: 30,
    targetSlPct: 80,
    targetAnswerSeconds: 20,
    shrinkagePct: 30,
  });
  assert(result.requiredAgents === 0, "no agents for zero calls");
  assert(result.projectedSlPct === 100, "empty interval is fully served");
});

test("CSV parser accepts a clean file", () => {
  const rows = parseForecastCsv("interval,calls_offered,aht_seconds\n08:00,100,180\n08:30,140,200");
  assert(rows.length === 2, "two rows");
  assert(rows[0].callsOffered === 100 && rows[1].ahtSeconds === 200, "values parsed");
});

test("CSV parser rejects a bad header", () => {
  let threw = false;
  try {
    parseForecastCsv("time,calls,aht\n08:00,100,180");
  } catch {
    threw = true;
  }
  assert(threw, "bad header should throw");
});

test("CSV parser rejects a duplicate interval", () => {
  let message = "";
  try {
    parseForecastCsv("interval,calls_offered,aht_seconds\n08:00,100,180\n08:00,90,180");
  } catch (err) {
    message = err instanceof Error ? err.message : "";
  }
  assert(message.includes("duplicate"), "duplicate interval should be named");
});

test("CSV parser rejects a non-positive AHT", () => {
  let threw = false;
  try {
    parseForecastCsv("interval,calls_offered,aht_seconds\n08:00,100,0");
  } catch {
    threw = true;
  }
  assert(threw, "zero AHT should throw");
});

test("plan CSV round-trips the headline numbers", () => {
  const results = planAll([{ interval: "08:00", callsOffered: 100, ahtSeconds: 180 }], {
    intervalMinutes: 30,
    targetSlPct: 80,
    targetAnswerSeconds: 20,
    shrinkagePct: 30,
  });
  const csv = toPlanCsv(results);
  assert(csv.split("\n")[0] === "interval,traffic_erlangs,required_agents,projected_sl_pct,occupancy_pct,scheduled_with_shrinkage", "header");
  assert(csv.includes("08:00,10.00,14,88.84,71.43,20"), "data row matches the worked example");
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
