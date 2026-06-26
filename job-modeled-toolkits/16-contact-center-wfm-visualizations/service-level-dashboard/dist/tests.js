"use strict";
/*
 * Test harness for the dashboard metrics. Loads metrics.js, runs assertions, and
 * prints PASS or FAIL on the page. Open tests.html to see it run.
 *
 * The headline case is the worked example in spec.md, the 08:00 row of the
 * sample actuals: 98 offered, 96 answered, 82 within the threshold, 1450 wait-
 * seconds, 17400 handle-seconds, 14 agents on a 30-minute interval. That gives
 * 83.67% service level, 2.04% abandon, 15.10s ASA, 181.25s AHT, 69.05% occupancy.
 */
const tests = [];
function test(name, run) {
    tests.push({ name, run });
}
function assert(condition, detail) {
    if (!condition) {
        throw new Error(detail);
    }
}
const config = { intervalMinutes: 30, targetSlPct: 80 };
function headlineRow() {
    return {
        interval: "08:00",
        callsOffered: 98,
        callsAnswered: 96,
        answeredWithinThreshold: 82,
        totalWaitSeconds: 1450,
        totalHandleSeconds: 17400,
        agentsScheduled: 14,
    };
}
test("worked example: service level is within over offered", () => {
    const m = computeInterval(headlineRow(), null, config);
    assert(m.slPct === 83.67, `expected 83.67, got ${m.slPct}`);
});
test("worked example: abandon, ASA, AHT, occupancy", () => {
    const m = computeInterval(headlineRow(), null, config);
    assert(m.abandonPct === 2.04, `abandon expected 2.04, got ${m.abandonPct}`);
    assert(m.asaSeconds === 15.1, `ASA expected 15.1, got ${m.asaSeconds}`);
    assert(m.ahtSeconds === 181.25, `AHT expected 181.25, got ${m.ahtSeconds}`);
    assert(m.occupancyPct === 69.05, `occupancy expected 69.05, got ${m.occupancyPct}`);
});
test("worked example clears the 80% target", () => {
    const m = computeInterval(headlineRow(), null, config);
    assert(m.breach === false, "83.67% should not be a breach");
});
test("an interval below target is flagged as a breach", () => {
    const row = {
        interval: "10:00",
        callsOffered: 305,
        callsAnswered: 270,
        answeredWithinThreshold: 205,
        totalWaitSeconds: 12000,
        totalHandleSeconds: 56700,
        agentsScheduled: 33,
    };
    const m = computeInterval(row, null, config);
    assert(m.slPct === 67.21, `expected 67.21, got ${m.slPct}`);
    assert(m.breach === true, "67.21% should be a breach against 80%");
});
test("coverage joins the plan by interval", () => {
    const plan = new Map([["08:00", 14]]);
    const m = computeInterval(headlineRow(), plan, config);
    assert(m.requiredAgents === 14, "required should come from the plan");
    assert(m.coverage === 0, "scheduled 14 minus required 14 is 0");
});
test("understaffing shows as negative coverage", () => {
    const plan = new Map([["10:00", 40]]);
    const row = {
        interval: "10:00",
        callsOffered: 305,
        callsAnswered: 270,
        answeredWithinThreshold: 205,
        totalWaitSeconds: 12000,
        totalHandleSeconds: 56700,
        agentsScheduled: 33,
    };
    const m = computeInterval(row, plan, config);
    assert(m.coverage === -7, `expected -7, got ${m.coverage}`);
});
test("a zero-volume interval reports full SL and no breach", () => {
    const row = {
        interval: "23:30",
        callsOffered: 0,
        callsAnswered: 0,
        answeredWithinThreshold: 0,
        totalWaitSeconds: 0,
        totalHandleSeconds: 0,
        agentsScheduled: 0,
    };
    const m = computeInterval(row, null, config);
    assert(m.slPct === 100 && m.breach === false, "empty interval is fully served");
    assert(m.occupancyPct === 0 && m.asaSeconds === 0, "no occupancy or wait on an empty interval");
});
test("overall service level is volume-weighted, not an average of percents", () => {
    const rows = [
        { interval: "08:00", callsOffered: 100, callsAnswered: 100, answeredWithinThreshold: 90, totalWaitSeconds: 500, totalHandleSeconds: 18000, agentsScheduled: 12 },
        { interval: "08:30", callsOffered: 300, callsAnswered: 300, answeredWithinThreshold: 210, totalWaitSeconds: 3000, totalHandleSeconds: 54000, agentsScheduled: 32 },
    ];
    const metrics = computeMetrics(rows, null, config);
    const s = summarize(metrics, rows);
    // 300 of 400 within threshold = 75.00, not the simple mean of 90 and 70.
    assert(s.overallSlPct === 75, `expected 75, got ${s.overallSlPct}`);
});
test("actuals parser accepts a clean file", () => {
    const rows = parseActualsCsv("interval,calls_offered,calls_answered,answered_within_threshold,total_wait_seconds,total_handle_seconds,agents_scheduled\n08:00,98,96,82,1450,17400,14");
    assert(rows.length === 1 && rows[0].agentsScheduled === 14, "row parsed");
});
test("actuals parser rejects answered greater than offered", () => {
    let message = "";
    try {
        parseActualsCsv("interval,calls_offered,calls_answered,answered_within_threshold,total_wait_seconds,total_handle_seconds,agents_scheduled\n08:00,90,95,80,1000,16000,12");
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("cannot exceed"), "should reject answered > offered");
});
test("actuals parser rejects a duplicate interval", () => {
    let threw = false;
    try {
        parseActualsCsv("interval,calls_offered,calls_answered,answered_within_threshold,total_wait_seconds,total_handle_seconds,agents_scheduled\n08:00,98,96,82,1450,17400,14\n08:00,90,88,80,1200,16000,13");
    }
    catch {
        threw = true;
    }
    assert(threw, "duplicate interval should throw");
});
test("plan parser maps interval to required agents", () => {
    const plan = parsePlanCsv("interval,traffic_erlangs,required_agents,projected_sl_pct,occupancy_pct,scheduled_with_shrinkage\n08:00,10.00,14,88.84,71.43,20");
    assert(plan.get("08:00") === 14, "required_agents read from the plan");
});
function runTests() {
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
        }
        catch (err) {
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
