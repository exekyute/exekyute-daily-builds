"use strict";
/*
 * Test harness for the Supplier Pareto and Savings Tracker logic. Loads
 * pareto.js, runs assertions, and prints PASS or FAIL on the page. Open
 * tests.html to see it run.
 *
 * The headline case is the worked example in spec.md. The supplier spend comes
 * straight from the Spend Analysis Dashboard's normalized export: Northwind
 * Supply leads at 65000.00 (47.81 percent), and the running share first reaches
 * 80 percent at Maple Logistics (91.54 percent), so three of the five suppliers
 * are the vital few. The savings list realizes 10945.00 against a 13300.00
 * target, an 82.29 percent attainment.
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
const SAVINGS = [
    "initiative_id,category,baseline_annual,current_annual,target_savings",
    "INIT-1,IT Hardware,70000.00,65000.00,4000.00",
    "INIT-2,Logistics,33000.00,29005.00,5000.00",
    "INIT-3,Professional Services,32000.00,30450.00,2000.00",
    "INIT-4,Office Supplies,9000.00,8000.00,1500.00",
    "INIT-5,Facilities,2000.00,2000.00,500.00",
    "INIT-6,Travel,4000.00,4600.00,300.00",
    "INIT-2,Logistics,33000.00,29005.00,5000.00",
    "INIT-9,,5000.00,4500.00,500.00",
].join("\n");
test("normalized spend totals by supplier", () => {
    const bySupplier = parseNormalizedCsv(NORMALIZED);
    assert(bySupplier.get("Northwind Supply") === 6500000, "Northwind 65000.00");
    assert(bySupplier.get("Maple Logistics") === 2900500, "Maple 29005.00");
    assert(bySupplier.size === 5, "five suppliers");
});
test("worked example: Northwind leads the Pareto at 47.81 percent", () => {
    const p = buildPareto(parseNormalizedCsv(NORMALIZED));
    assert(p.totalCents === 13595500, "total 135955.00");
    assert(p.rows[0].supplier === "Northwind Supply", "Northwind first");
    assert(p.rows[0].cents === 6500000, "Northwind 65000.00, agreeing with the dashboard");
    assert(p.rows[0].pct === 47.81, "Northwind 47.81 percent");
    assert(p.rows[0].cumulativePct === 47.81, "running share 47.81 percent");
});
test("the running share reaches 80 percent at Maple Logistics", () => {
    const p = buildPareto(parseNormalizedCsv(NORMALIZED));
    assert(p.rows[1].cumulativePct === 70.21, "Granite IT brings it to 70.21 percent");
    assert(p.rows[2].supplier === "Maple Logistics", "Maple is third");
    assert(p.rows[2].cumulativePct === 91.54, "Maple brings it to 91.54 percent");
});
test("worked example: three suppliers are the vital few at 91.54 percent", () => {
    const p = buildPareto(parseNormalizedCsv(NORMALIZED));
    assert(p.vitalFewCount === 3, "three vital-few suppliers");
    assert(p.rows[0].vitalFew && p.rows[1].vitalFew && p.rows[2].vitalFew, "the top three are vital few");
    assert(!p.rows[3].vitalFew && !p.rows[4].vitalFew, "Cedar and Harbour are the long tail");
    assert(p.vitalFewPct === 91.54, "the vital few make up 91.54 percent of spend");
});
test("savings: realized and target reconcile, with an overrun carried through", () => {
    const s = parseSavingsCsv(SAVINGS);
    assert(s.rows.length === 6, "six valid initiatives");
    const init1 = s.rows.find((r) => r.id === "INIT-1");
    assert(init1.realizedCents === 500000 && init1.attainmentPct === 125, "INIT-1 realized 5000.00, 125 percent");
    const init6 = s.rows.find((r) => r.id === "INIT-6");
    assert(init6.realizedCents === -60000, "INIT-6 is an overrun of -600.00");
    assert(init6.attainmentPct === -200 && !init6.met, "INIT-6 attainment -200 percent, target not met");
});
test("worked example: savings realize 10945.00 against 13300.00, 82.29 percent", () => {
    const s = parseSavingsCsv(SAVINGS);
    assert(s.totalTargetCents === 1330000, "target 13300.00");
    assert(s.totalRealizedCents === 1094500, "realized 10945.00");
    assert(s.overallAttainmentPct === 82.29, "overall attainment 82.29 percent");
});
test("a zero-realized initiative sits at the boundary", () => {
    const s = parseSavingsCsv(SAVINGS);
    const init5 = s.rows.find((r) => r.id === "INIT-5");
    assert(init5.realizedCents === 0 && init5.attainmentPct === 0, "INIT-5 realized 0, attainment 0 percent");
    assert(!init5.met, "a 500.00 target with 0 realized is not met");
});
test("duplicate and missing-field initiatives are skipped with warnings", () => {
    const s = parseSavingsCsv(SAVINGS);
    assert(s.warnings.length === 2, "two warnings");
    assert(s.warnings.some((w) => w.message.includes("repeats")), "the duplicate INIT-2 is named");
    assert(s.warnings.some((w) => w.id === "INIT-9"), "the category-less INIT-9 is named");
});
test("an initiative with no target reports no attainment instead of dividing by zero", () => {
    const s = parseSavingsCsv("initiative_id,category,baseline_annual,current_annual,target_savings\nINIT-X,Misc,1000.00,900.00,0.00");
    assert(s.rows[0].attainmentPct === null, "no target means no attainment percentage");
    assert(s.overallAttainmentPct === null, "overall attainment is null when total target is zero");
});
test("the Pareto rejects a file that is not the normalized export", () => {
    let threw = false;
    try {
        parseNormalizedCsv("supplier,amount\nNorthwind,100.00");
    }
    catch {
        threw = true;
    }
    assert(threw, "a foreign header should throw");
});
test("the savings tracker rejects a non-numeric amount", () => {
    let message = "";
    try {
        parseSavingsCsv("initiative_id,category,baseline_annual,current_annual,target_savings\nINIT-1,IT,lots,900.00,100.00");
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("dollar figure"), "a non-numeric amount should be named");
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
