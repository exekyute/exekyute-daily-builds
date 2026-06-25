"use strict";
/*
 * Test harness for the PO/Invoice Compliance logic. Loads compliance.js, runs
 * assertions, and prints PASS or FAIL on the page. Open tests.html to see it run.
 *
 * The headline case is the worked example in spec.md. Across the twelve clean
 * lines the Spend Analysis Dashboard exports, two run off-contract for 10000.00,
 * two fail the three-way match for 15450.00, and the remaining eight are fully
 * compliant, a 66.67 percent compliant rate.
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
// The exact normalized-spend.csv the Spend Analysis Dashboard exports.
const NORMALIZED = [
    "line_id,supplier,category,contract_id,on_contract,po_amount,received_amount,invoice_amount,invoice_date",
    "L001,Northwind Supply,IT Hardware,C-1001,Y,40000.00,40000.00,40000.00,2026-01-15",
    "L002,Northwind Supply,IT Hardware,C-1001,Y,25000.00,25000.00,25000.00,2026-02-10",
    "L003,Granite IT,Professional Services,C-1002,Y,18000.00,18000.00,18000.00,2026-01-20",
    "L004,Granite IT,Professional Services,C-1002,Y,12000.00,12000.00,12450.00,2026-02-05",
    "L005,Maple Logistics,Logistics,C-1003,Y,15000.00,15000.00,15000.00,2026-01-25",
    "L006,Maple Logistics,Logistics,,N,8000.00,8000.00,8000.00,2026-02-12",
    "L007,Cedar Office,Office Supplies,C-1004,Y,5000.00,5000.00,5000.00,2026-01-30",
    "L008,Cedar Office,Office Supplies,C-1004,Y,3000.00,2950.00,3000.00,2026-02-15",
    "L009,Harbour Freight Co,Facilities,,N,2000.00,2000.00,2000.00,2026-02-18",
    "L010,Harbour Freight Co,Facilities,C-1005,Y,0.00,0.00,0.00,2026-02-20",
    "L013,Cedar Office,Stationery,C-1004,Y,1500.00,1500.00,1500.00,2026-02-23",
    "L014,Maple Logistics,Logistics,C-1003,Y,6000.00,6000.00,6005.00,2026-02-24",
].join("\n");
function judged() {
    return parseAndJudge(NORMALIZED);
}
test("the tolerance is the greater of 5.00 or 1 percent of the PO", () => {
    assert(toleranceFor(1200000) === 12000, "1 percent of 12000.00 is 120.00");
    assert(toleranceFor(300000) === 3000, "1 percent of 3000.00 is 30.00");
    assert(toleranceFor(0) === 500, "the floor is 5.00 when the PO is 0");
    assert(toleranceFor(40000) === 500, "1 percent of 400.00 is below the 5.00 floor");
});
test("a line where PO, receipt, and invoice agree passes the match", () => {
    const l001 = judged().find((l) => l.lineId === "L001");
    assert(l001.matched && l001.onContract, "L001 is matched and on-contract");
    assert(l001.reasons.length === 0, "a compliant line carries no reasons");
});
test("a blank contract reads as off-contract spend", () => {
    const l006 = judged().find((l) => l.lineId === "L006");
    assert(l006.offContract, "L006 is off-contract");
    assert(l006.reasons.indexOf("off-contract spend") !== -1, "the reason is named");
    assert(l006.matched, "L006 still passes the three-way match");
});
test("worked example: an invoice over the PO is a match exception (L004)", () => {
    const l004 = judged().find((l) => l.lineId === "L004");
    assert(!l004.matched, "L004 fails the match");
    assert(l004.reasons.some((r) => r.indexOf("invoice exceeds PO by 450.00") !== -1), "invoice over PO by 450.00");
    assert(l004.reasons.some((r) => r.indexOf("invoice exceeds receipt by 450.00") !== -1), "invoice over receipt by 450.00");
});
test("worked example: an invoice over the receipt is a match exception (L008)", () => {
    const l008 = judged().find((l) => l.lineId === "L008");
    assert(!l008.matched, "L008 fails the match");
    assert(l008.reasons.some((r) => r.indexOf("invoice exceeds receipt by 50.00") !== -1), "invoice over receipt by 50.00");
    assert(l008.reasons.some((r) => r.indexOf("receipt short of PO by 50.00") !== -1), "receipt short of PO by 50.00");
});
test("a small difference inside tolerance still matches (L014 boundary)", () => {
    const l014 = judged().find((l) => l.lineId === "L014");
    assert(l014.toleranceCents === 6000, "tolerance is 60.00 on a 6000.00 PO");
    assert(l014.matched, "a 5.00 invoice difference is within the 60.00 tolerance");
    assert(l014.reasons.length === 0, "no reasons on a matched line");
});
test("a zero-amount line passes the match (L010 boundary)", () => {
    const l010 = judged().find((l) => l.lineId === "L010");
    assert(l010.matched && l010.onContract, "L010 is compliant");
});
test("worked example: 2 off-contract, 2 exceptions, 8 compliant", () => {
    const summary = summarize(judged());
    assert(summary.totalLines === 12, "twelve lines");
    assert(summary.offContractLines === 2 && summary.offContractCents === 1000000, "off-contract 10000.00 over 2 lines");
    assert(summary.exceptionLines === 2 && summary.exceptionCents === 1545000, "exceptions 15450.00 over 2 lines");
    assert(summary.compliantLines === 8, "eight fully compliant lines");
    assert(summary.compliantPct === 66.67, "66.67 percent compliant");
});
test("the flagged list holds exactly the off-contract and exception lines", () => {
    const flagged = flaggedOnly(judged()).map((l) => l.lineId);
    assert(flagged.length === 4, "four flagged lines");
    assert(flagged.indexOf("L004") !== -1 && flagged.indexOf("L008") !== -1, "both exceptions are listed");
    assert(flagged.indexOf("L006") !== -1 && flagged.indexOf("L009") !== -1, "both off-contract lines are listed");
});
test("total invoice agrees with the dashboard to the cent", () => {
    const summary = summarize(judged());
    assert(summary.totalInvoiceCents === 13595500, "total 135955.00, the same figure the dashboard reports");
});
test("a bad on_contract flag rejects the file", () => {
    let message = "";
    try {
        parseAndJudge("line_id,supplier,category,contract_id,on_contract,po_amount,received_amount,invoice_amount,invoice_date\nL001,X,Y,C-1,maybe,1.00,1.00,1.00,2026-01-15");
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.indexOf("must be Y or N") !== -1, "the on_contract value should be named");
});
test("a foreign header rejects the file", () => {
    let threw = false;
    try {
        parseAndJudge("po,invoice\n1.00,1.00");
    }
    catch {
        threw = true;
    }
    assert(threw, "a file that is not the normalized export should throw");
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
