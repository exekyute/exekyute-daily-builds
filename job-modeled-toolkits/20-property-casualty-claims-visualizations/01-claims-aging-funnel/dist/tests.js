"use strict";
/*
 * Test harness for the claims-aging logic. Loads aging.js, runs assertions, and
 * prints PASS or FAIL on the page. Open tests.html to see it run.
 *
 * The headline numbers match the worked example in spec.md: as of 2024-12-31 the
 * register holds ten claims (five open, two pending, three closed), the still-open
 * inventory spreads across the age buckets as 1 / 0 / 1 / 2 / 3, and the three
 * closed claims took 828, 568, and 938 days to close, an average of 778.
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
// The clean sample register, inline so the tests do not depend on a file load.
const SAMPLE_REGISTER = [
    "claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,earned_premium",
    "A-2201,Auto,2022,2022-03-10,2022-12-31,12,open,,8000.00,4000.00,25000.00",
    "A-2201,Auto,2022,2022-03-10,2023-12-31,24,open,,11000.00,1000.00,25000.00",
    "A-2201,Auto,2022,2022-03-10,2024-12-31,36,closed,2024-06-15,12000.00,0.00,25000.00",
    "A-2202,Auto,2022,2022-08-01,2022-12-31,12,open,,2000.00,3000.00,25000.00",
    "A-2202,Auto,2022,2022-08-01,2023-12-31,24,open,,4500.00,500.00,25000.00",
    "A-2202,Auto,2022,2022-08-01,2024-12-31,36,closed,2024-02-20,5000.00,0.00,25000.00",
    "A-2301,Auto,2023,2023-05-12,2023-12-31,12,open,,3000.00,7000.00,30000.00",
    "A-2301,Auto,2023,2023-05-12,2024-12-31,24,open,,6000.00,5000.00,30000.00",
    "A-2302,Auto,2023,2023-11-30,2023-12-31,12,open,,1000.00,4000.00,30000.00",
    "A-2302,Auto,2023,2023-11-30,2024-12-31,24,pending,,2500.00,3500.00,30000.00",
    "A-2401,Auto,2024,2024-09-15,2024-12-31,12,open,,1500.00,6500.00,18000.00",
    "A-2402,Auto,2024,2024-12-01,2024-12-31,12,open,,500.00,2000.00,18000.00",
    "A-2403,Auto,2024,2024-10-02,2024-12-31,12,pending,,0.00,3000.00,18000.00",
    "P-2201,Property,2022,2022-02-15,2022-12-31,12,open,,20000.00,10000.00,40000.00",
    "P-2201,Property,2022,2022-02-15,2023-12-31,24,open,,28000.00,2000.00,40000.00",
    "P-2201,Property,2022,2022-02-15,2024-12-31,36,closed,2024-09-10,30000.00,0.00,40000.00",
    "P-2301,Property,2023,2023-07-20,2023-12-31,12,open,,5000.00,15000.00,35000.00",
    "P-2301,Property,2023,2023-07-20,2024-12-31,24,open,,12000.00,10000.00,35000.00",
    "P-2401,Property,2024,2024-08-05,2024-12-31,12,open,,4000.00,16000.00,28000.00",
].join("\n");
function sampleSummary() {
    return summarize(parseRegisterCsv(SAMPLE_REGISTER));
}
test("money parses to exact cents", () => {
    const rows = parseRegisterCsv("claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,earned_premium\nC1,Auto,2024,2024-01-01,2024-12-31,12,open,,50.05,0.00,1000.00");
    assert(rows[0].paidCents === 5005, "50.05 should be 5005 cents");
    assert(rows[0].reserveCents === 0, "0.00 should be 0 cents");
});
test("the as-of date is the latest valuation", () => {
    assert(sampleSummary().asOf === "2024-12-31", "as-of should be 2024-12-31");
});
test("ten claims roll up from the register", () => {
    assert(sampleSummary().totalClaims === 10, "ten claims expected");
});
test("status mix is five open, two pending, three closed", () => {
    const s = sampleSummary().statusCounts;
    assert(s.open === 5 && s.pending === 2 && s.closed === 3, `got ${s.open}/${s.pending}/${s.closed}`);
});
test("the open inventory spreads across buckets as 1 / 0 / 1 / 2 / 3", () => {
    const counts = sampleSummary().buckets.map((b) => b.count);
    assert(counts.join(",") === "1,0,1,2,3", `buckets were ${counts.join(",")}`);
});
test("a 30-day-old claim lands in the 0-30 bucket (boundary)", () => {
    const b = sampleSummary().buckets.find((x) => x.label === "0-30");
    assert(b !== undefined && b.count === 1, "A-2402 at 30 days belongs in 0-30");
});
test("a 90-day-old claim lands in the 61-90 bucket (boundary)", () => {
    const b = sampleSummary().buckets.find((x) => x.label === "61-90");
    assert(b !== undefined && b.count === 1, "A-2403 at 90 days belongs in 61-90");
});
test("average days to close is 778 over three closed claims", () => {
    const s = sampleSummary();
    assert(s.closedCount === 3, "three closed claims expected");
    assert(s.avgDaysToClose === 778, `average was ${s.avgDaysToClose}`);
});
test("incurred at the latest valuation totals 119,500.00", () => {
    assert(sampleSummary().totalIncurredCents === 11950000, "incurred should be 11950000 cents");
});
test("paid at the latest valuation totals 73,500.00", () => {
    assert(sampleSummary().totalPaidCents === 7350000, "paid should be 7350000 cents");
});
test("clean CSV marks one latest row per claim and carries incurred", () => {
    const csv = toCleanCsv(parseRegisterCsv(SAMPLE_REGISTER));
    const lines = csv.split("\n");
    assert(lines[0].startsWith("claim_id,line_of_business,accident_period"), "header present");
    assert(lines[0].endsWith("is_latest,age_days,age_bucket,days_to_close"), "enriched columns present");
    const latestCount = lines.slice(1).filter((l) => l.split(",")[12] === "Y").length;
    assert(latestCount === 10, `expected 10 latest rows, got ${latestCount}`);
    assert(csv.includes("A-2201,Auto,2022,2022-03-10,2024-12-31,36,closed,2024-06-15,12000.00,0.00,12000.00,25000.00,Y,"), "A-2201 latest row matches");
});
test("parser rejects a bad header", () => {
    let threw = false;
    try {
        parseRegisterCsv("id,line,year\nA,B,C");
    }
    catch {
        threw = true;
    }
    assert(threw, "bad header should throw");
});
test("parser rejects a negative case reserve", () => {
    let message = "";
    try {
        parseRegisterCsv("claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,earned_premium\nC1,Auto,2024,2024-01-01,2024-12-31,12,open,,1200.00,-500.00,18000.00");
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("case_reserve"), "negative reserve should be named");
});
test("parser rejects a closed claim with no close date", () => {
    let message = "";
    try {
        parseRegisterCsv("claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,earned_premium\nC1,Auto,2024,2024-01-01,2024-12-31,12,closed,,1200.00,0.00,18000.00");
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("close_date"), "missing close date should be named");
});
test("parser rejects an unknown status", () => {
    let message = "";
    try {
        parseRegisterCsv("claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,earned_premium\nC1,Auto,2024,2024-01-01,2024-12-31,12,settled,,1200.00,0.00,18000.00");
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("status"), "unknown status should be named");
});
test("parser rejects a duplicate valuation for one claim", () => {
    let message = "";
    try {
        parseRegisterCsv("claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,earned_premium\nC1,Auto,2024,2024-01-01,2024-12-31,12,open,,1200.00,0.00,18000.00\nC1,Auto,2024,2024-01-01,2024-12-31,12,open,,1300.00,0.00,18000.00");
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("already has a valuation"), "duplicate valuation should be named");
});
test("parser rejects falling cumulative paid", () => {
    let message = "";
    try {
        parseRegisterCsv("claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,earned_premium\nC1,Auto,2024,2023-01-01,2023-12-31,12,open,,5000.00,0.00,18000.00\nC1,Auto,2024,2023-01-01,2024-12-31,24,open,,4000.00,0.00,18000.00");
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("falls from development month"), "falling paid should be named");
});
test("parser rejects inconsistent earned premium within a line and year", () => {
    let message = "";
    try {
        parseRegisterCsv("claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,earned_premium\nC1,Auto,2024,2024-01-01,2024-12-31,12,open,,1200.00,0.00,18000.00\nC2,Auto,2024,2024-02-01,2024-12-31,12,open,,800.00,0.00,19000.00");
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("earned_premium"), "inconsistent premium should be named");
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
