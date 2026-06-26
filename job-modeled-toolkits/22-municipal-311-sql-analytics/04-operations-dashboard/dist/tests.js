"use strict";
/*
 * Test harness for the dashboard logic. Loads dashboard.js, runs assertions, and
 * prints PASS or FAIL on the page. Open tests.html to see it run.
 *
 * The headline cases are the worked examples from the SQL specs: Roads in 2025-01
 * opens at 2, adds 4, closes 3, and closes the month at 3; the cost to serve totals
 * $708.50; five requests are open with four overdue; and the overall time to close
 * averages 11.22 days. The numbers here must match the SQL runners to the cent.
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
function assertEqual(actual, expected, detail) {
    if (actual !== expected) {
        throw new Error(detail + " (got " + JSON.stringify(actual) + ", expected " + JSON.stringify(expected) + ")");
    }
}
const PERIOD_CSV = [
    "period,department,opening,new_requests,closed,closing,cost_to_serve_cents",
    "2024-12,Bylaw,0,1,0,1,0",
    "2024-12,Parks,0,0,0,0,0",
    "2024-12,Roads,0,2,0,2,0",
    "2025-01,Bylaw,1,2,2,1,10525",
    "2025-01,Parks,0,1,0,1,0",
    "2025-01,Roads,2,4,3,3,25650",
    "2025-02,Bylaw,1,1,2,0,10525",
    "2025-02,Parks,1,1,0,2,0",
    "2025-02,Roads,3,2,2,3,24150",
].join("\n");
const AGING_CSV = [
    "bucket,open_count,overdue",
    "0-7,0,0",
    "8-14,1,0",
    "15-30,1,1",
    "31+,3,3",
].join("\n");
const CATEGORY_CSV = [
    "category,closed_count,total_days,target_days,breaches",
    "Graffiti,2,34,14,2",
    "NoiseComplaint,2,5,5,0",
    "Pothole,3,28,7,1",
    "Streetlight,2,34,10,2",
].join("\n");
const BAD_PERIOD_CSV = PERIOD_CSV.replace("2025-01,Roads,2,4,3,3,25650", "2025-01,Roads,2,4,3,9,25650");
test("detects each file by its header", () => {
    assertEqual(detectKind(splitCsv(PERIOD_CSV)[0]), "period", "period summary detected");
    assertEqual(detectKind(splitCsv(AGING_CSV)[0]), "aging", "aging detected");
    assertEqual(detectKind(splitCsv(CATEGORY_CSV)[0]), "category", "category detected");
    assertEqual(detectKind(["foo", "bar"]), "unknown", "unknown header rejected");
});
test("flow identity holds for every clean row", () => {
    const rows = parsePeriodRows(splitCsv(PERIOD_CSV));
    assertEqual(rows.length, 9, "nine department-month rows");
    assertEqual(identityFailures(rows).length, 0, "no identity failures in clean data");
});
test("worked example: Roads 2025-01", () => {
    const rows = parsePeriodRows(splitCsv(PERIOD_CSV));
    const roads = rows.filter((r) => r.period === "2025-01" && r.department === "Roads")[0];
    assertEqual(roads.opening, 2, "opening");
    assertEqual(roads.newRequests, 4, "new");
    assertEqual(roads.closed, 3, "closed");
    assertEqual(roads.closing, 3, "closing");
    assert(identityHolds(roads), "identity holds for Roads 2025-01");
    assertEqual(roads.costToServeCents, 25650, "Roads January cost in cents");
    assertEqual(formatCadFromCents(roads.costToServeCents), "$256.50", "Roads January cost formatted");
});
test("cost to serve totals $708.50 to the cent", () => {
    const rows = parsePeriodRows(splitCsv(PERIOD_CSV));
    assertEqual(totalCostCents(rows), 70850, "grand total cents");
    assertEqual(formatCadFromCents(totalCostCents(rows)), "$708.50", "grand total formatted");
});
test("open aging totals five open, four overdue", () => {
    const rows = parseAgingRows(splitCsv(AGING_CSV));
    assertEqual(totalOpen(rows), 5, "total open");
    assertEqual(totalOverdue(rows), 4, "total overdue");
});
test("time to close averages 11.22 days overall", () => {
    const rows = parseCategoryRows(splitCsv(CATEGORY_CSV));
    assertEqual(formatHundredths(overallAvgDaysHundredths(rows)), "11.22", "overall average");
    const pothole = rows.filter((r) => r.category === "Pothole")[0];
    assertEqual(formatHundredths(avgDaysHundredths(pothole.totalDays, pothole.closedCount)), "9.33", "pothole average");
    assertEqual(totalBreaches(rows), 5, "total breaches");
});
test("a broken closing value is caught as an identity failure", () => {
    const rows = parsePeriodRows(splitCsv(BAD_PERIOD_CSV));
    const failures = identityFailures(rows);
    assertEqual(failures.length, 1, "one identity failure");
    assertEqual(failures[0].department, "Roads", "the Roads row fails");
});
function runTests() {
    const root = document.getElementById("results");
    if (!root) {
        return;
    }
    let passed = 0;
    const items = [];
    for (const testCase of tests) {
        try {
            testCase.run();
            passed++;
            items.push('<li class="pass">PASS ' + testCase.name + "</li>");
        }
        catch (err) {
            const message = err instanceof Error ? err.message : String(err);
            items.push('<li class="fail">FAIL ' + testCase.name + ": " + message + "</li>");
        }
    }
    const allPassed = passed === tests.length;
    const summary = '<p class="summary ' + (allPassed ? "pass" : "fail") + '">' +
        passed + " of " + tests.length + " passed" +
        "</p>";
    root.innerHTML = summary + "<ul>" + items.join("") + "</ul>";
}
document.addEventListener("DOMContentLoaded", runTests);
