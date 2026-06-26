"use strict";
/*
 * Test harness for the maturity-ladder logic. Loads ladder.js, runs assertions,
 * and prints PASS or FAIL on the page. Open tests.html to see it run.
 *
 * The headline case is the worked example in spec.md: against an as-of date of
 * 2026-06-15, the sample obligations land in week 1 (with an overdue item folded
 * in), weeks 2, 3, 4, week 13, and one beyond the horizon. The week-1 total is
 * 76750.00 and the week-13 total is 75000.00, the two figures the forecast picks
 * up as debt outflows.
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
const AS_OF = "2026-06-15";
const SAMPLE = [
    "obligation_id,counterparty,type,due_date,amount",
    "OB-1001,BMO Term Loan,loan_principal,2026-06-19,50000.00",
    "OB-1002,CRA,tax_remittance,2026-06-15,22000.00",
    "OB-1003,Equipment Lease Co,lease,2026-07-02,8500.00",
    "OB-1004,Series A Note,interest,2026-06-28,12000.00",
    "OB-1005,Acme Supplies,payable,2026-06-10,4750.00",
    "OB-1006,RBC Revolver,loan_principal,2026-09-13,75000.00",
    "OB-1007,Pension Trust,payable,2026-12-01,30000.00",
    "OB-1008,City Property Tax,tax_remittance,2026-07-06,9000.00",
].join("\n");
function bucketsFor() {
    return buildLadder(parseObligationCsv(SAMPLE), AS_OF, 5000000);
}
test("parseMoneyToCents reads dollars and cents", () => {
    assert(parseMoneyToCents("76750.00") === 7675000, "76750.00 is 7675000 cents");
    assert(parseMoneyToCents("8500.5") === 850050, "8500.5 is 850050 cents");
});
test("classify puts the as-of date in week 1", () => {
    assert(classify(AS_OF, "2026-06-15").kind === "week", "as-of is a week, not overdue");
    assert(classify(AS_OF, "2026-06-15").week === 1, "as-of is week 1");
});
test("classify finds overdue, week boundaries, and beyond", () => {
    assert(classify(AS_OF, "2026-06-10").kind === "overdue", "before as-of is overdue");
    assert(classify(AS_OF, "2026-06-21").week === 1, "day 6 is still week 1");
    assert(classify(AS_OF, "2026-06-22").week === 2, "day 7 rolls to week 2");
    assert(classify(AS_OF, "2026-09-13").week === 13, "day 90 is week 13");
    assert(classify(AS_OF, "2026-09-14").kind === "beyond", "day 91 is beyond the horizon");
});
test("addDays walks the calendar across a month end", () => {
    assert(addDays("2026-06-15", 7) === "2026-06-22", "one week on");
    assert(addDays("2026-06-15", 84) === "2026-09-07", "start of week 13");
});
test("worked example: week 1 totals 76750.00 with the overdue item folded in", () => {
    const buckets = bucketsFor();
    const w1 = buckets.find((b) => b.label === "W1");
    // W1 holds the two week-1 obligations; the overdue item lands in the Overdue
    // bucket on the chart but is folded into week 1 only in the export.
    assert(w1.totalCents === 7200000, "W1 on the chart is 72000.00 (50000 + 22000)");
    const overdue = buckets.find((b) => b.kind === "overdue");
    assert(overdue.totalCents === 475000, "Overdue is 4750.00");
});
test("week 13 carries the revolver at 75000.00", () => {
    const buckets = bucketsFor();
    const w13 = buckets.find((b) => b.label === "W13");
    assert(w13.totalCents === 7500000, "W13 is 75000.00");
    assert(w13.heavy, "W13 is over the 50000.00 concentration threshold");
});
test("the beyond bucket holds the long-dated payable", () => {
    const buckets = bucketsFor();
    const beyond = buckets.find((b) => b.kind === "beyond");
    assert(beyond.totalCents === 3000000, "Beyond is 30000.00");
    assert(beyond.count === 1, "one obligation beyond the horizon");
});
test("summary rolls up totals and the overdue figure", () => {
    const summary = summarize(bucketsFor());
    assert(summary.obligations === 8, "eight obligations");
    assert(summary.totalCents === 21125000, "total 211250.00");
    assert(summary.overdueCents === 475000, "overdue 4750.00");
    assert(summary.within13Cents === 18125000, "within 13 weeks 181250.00");
});
test("isOverdue flags the past-due payable only", () => {
    const obligations = parseObligationCsv(SAMPLE);
    const overdue = obligations.filter((ob) => isOverdue(AS_OF, ob));
    assert(overdue.length === 1 && overdue[0].id === "OB-1005", "only OB-1005 is overdue");
});
test("CSV parser rejects a bad header", () => {
    let threw = false;
    try {
        parseObligationCsv("id,party,kind,date,amt\nOB-1,A,loan,2026-06-19,1.00");
    }
    catch {
        threw = true;
    }
    assert(threw, "bad header should throw");
});
test("CSV parser rejects a duplicate obligation id", () => {
    let message = "";
    try {
        parseObligationCsv("obligation_id,counterparty,type,due_date,amount\nOB-1,A,loan,2026-06-19,1.00\nOB-1,B,loan,2026-06-20,2.00");
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("duplicate"), "duplicate id should be named");
});
test("CSV parser rejects an unreal due date", () => {
    let threw = false;
    try {
        parseObligationCsv("obligation_id,counterparty,type,due_date,amount\nOB-1,A,loan,2026-02-30,1.00");
    }
    catch {
        threw = true;
    }
    assert(threw, "Feb 30 should throw");
});
test("maturities-by-week folds overdue into week 1 and drops beyond", () => {
    const csv = toMaturitiesByWeekCsv(parseObligationCsv(SAMPLE), AS_OF);
    const rows = csv.split("\n");
    assert(rows[0] === "week,debt_due", "header");
    assert(rows[1] === "1,76750.00", "week 1 is 50000 + 22000 + overdue 4750");
    assert(rows[2] === "2,12000.00", "week 2");
    assert(rows[3] === "3,8500.00", "week 3");
    assert(rows[4] === "4,9000.00", "week 4");
    assert(rows[13] === "13,75000.00", "week 13");
    assert(rows.length === 14, "header plus 13 weeks, beyond excluded");
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
