"use strict";
/*
 * Test harness for the MRR movement logic. Loads movement.js, runs assertions,
 * and prints PASS or FAIL on the page. Open tests.html to see it run.
 *
 * The headline case is the worked example in spec.md: for April 2025 the ledger
 * opens at 2,500.00, adds 250.00 new and 100.00 expansion, loses 50.00 to
 * contraction and 50.00 to churn, and closes at 2,750.00.
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
// The clean sample ledger, inline so the tests do not depend on a file load.
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
function aprilRow() {
    const rows = computeMovement(parseLedgerCsv(SAMPLE_LEDGER));
    const april = rows.find((r) => r.month === "2025-04");
    if (!april) {
        throw new Error("April row missing");
    }
    return april;
}
test("money parses to exact cents", () => {
    const rows = parseLedgerCsv("customer_id,plan,signup_month,month,mrr\nC001,Pro,2025-01,2025-01,50.05");
    assert(rows[0].mrrCents === 5005, "50.05 should be 5005 cents");
});
test("worked example: April opens at 2,500.00", () => {
    assert(aprilRow().openingCents === 250000, "opening should be 250000 cents");
});
test("worked example: April adds 250.00 new", () => {
    assert(aprilRow().newCents === 25000, "new should be 25000 cents");
});
test("worked example: April adds 100.00 expansion", () => {
    assert(aprilRow().expansionCents === 10000, "expansion should be 10000 cents");
});
test("worked example: April loses 50.00 to contraction", () => {
    assert(aprilRow().contractionCents === 5000, "contraction should be 5000 cents");
});
test("worked example: April loses 50.00 to churn", () => {
    assert(aprilRow().churnedCents === 5000, "churn should be 5000 cents");
});
test("worked example: April closes at 2,750.00", () => {
    assert(aprilRow().closingCents === 275000, "closing should be 275000 cents");
});
test("the movement identity holds every month", () => {
    const rows = computeMovement(parseLedgerCsv(SAMPLE_LEDGER));
    for (const r of rows) {
        const expected = r.openingCents + r.newCents + r.expansionCents - r.contractionCents - r.churnedCents;
        assert(expected === r.closingCents, `identity fails in ${r.month}`);
    }
});
test("the first month opens at zero and is all new", () => {
    const rows = computeMovement(parseLedgerCsv(SAMPLE_LEDGER));
    const jan = rows[0];
    assert(jan.month === "2025-01", "first month is January");
    assert(jan.openingCents === 0, "January opens at zero");
    assert(jan.newCents === jan.closingCents, "January closing is all new");
});
test("parser rejects a bad header", () => {
    let threw = false;
    try {
        parseLedgerCsv("id,plan,start,month,amount\nC001,Pro,2025-01,2025-01,50.00");
    }
    catch {
        threw = true;
    }
    assert(threw, "bad header should throw");
});
test("parser rejects an unknown plan", () => {
    let message = "";
    try {
        parseLedgerCsv("customer_id,plan,signup_month,month,mrr\nC001,Gold,2025-01,2025-01,50.00");
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("plan"), "unknown plan should be named");
});
test("parser rejects a non-positive MRR", () => {
    let threw = false;
    try {
        parseLedgerCsv("customer_id,plan,signup_month,month,mrr\nC001,Pro,2025-01,2025-01,0");
    }
    catch {
        threw = true;
    }
    assert(threw, "zero MRR should throw");
});
test("parser rejects a duplicate customer-month", () => {
    let message = "";
    try {
        parseLedgerCsv("customer_id,plan,signup_month,month,mrr\nC001,Pro,2025-01,2025-01,50.00\nC001,Pro,2025-01,2025-01,60.00");
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("already has a row"), "duplicate should be named");
});
test("parser rejects a month before signup", () => {
    let threw = false;
    try {
        parseLedgerCsv("customer_id,plan,signup_month,month,mrr\nC001,Pro,2025-03,2025-01,50.00");
    }
    catch {
        threw = true;
    }
    assert(threw, "month before signup should throw");
});
test("movement CSV round-trips the April row", () => {
    const csv = toMovementCsv(computeMovement(parseLedgerCsv(SAMPLE_LEDGER)));
    assert(csv.split("\n")[0] === "month,opening_mrr,new_mrr,expansion_mrr,contraction_mrr,churned_mrr,closing_mrr", "header");
    assert(csv.includes("2025-04,2500.00,250.00,100.00,50.00,50.00,2750.00"), "April row matches the worked example");
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
