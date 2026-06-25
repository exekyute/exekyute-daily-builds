"use strict";
/*
 * Test harness for the spend-analysis logic. Loads spend.js, runs assertions,
 * and prints PASS or FAIL on the page. Open tests.html to see it run.
 *
 * The headline case is the worked example in spec.md. The twelve clean sample
 * lines total 135955.00. Northwind Supply is the largest supplier at 65000.00,
 * a 47.81 percent share, and that 65000.00 is the figure the Supplier Pareto
 * view reads back from the normalized export.
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
const SAMPLE = [
    "line_id,supplier,category,contract_id,po_amount,received_amount,invoice_amount,invoice_date",
    "L001,Northwind Supply,IT Hardware,C-1001,40000.00,40000.00,40000.00,2026-01-15",
    "L002,Northwind Supply,IT Hardware,C-1001,25000.00,25000.00,25000.00,2026-02-10",
    "L003,Granite IT,Professional Services,C-1002,18000.00,18000.00,18000.00,2026-01-20",
    "L004,Granite IT,Professional Services,C-1002,12000.00,12000.00,12450.00,2026-02-05",
    "L005,Maple Logistics,Logistics,C-1003,15000.00,15000.00,15000.00,2026-01-25",
    "L006,Maple Logistics,Logistics,,8000.00,8000.00,8000.00,2026-02-12",
    "L007,Cedar Office,Office Supplies,C-1004,5000.00,5000.00,5000.00,2026-01-30",
    "L008,Cedar Office,Office Supplies,C-1004,3000.00,2950.00,3000.00,2026-02-15",
    "L009,Harbour Freight Co,Facilities,,2000.00,2000.00,2000.00,2026-02-18",
    "L010,Harbour Freight Co,Facilities,C-1005,0.00,0.00,0.00,2026-02-20",
    "L001,Northwind Supply,IT Hardware,C-1001,40000.00,40000.00,40000.00,2026-01-15",
    "L012,,Office Supplies,C-1006,1000.00,1000.00,1000.00,2026-02-22",
    "L013,Cedar Office,Stationery,C-1004,1500.00,1500.00,1500.00,2026-02-23",
    "L014,Maple Logistics,Logistics,C-1003,6000.00,6000.00,6005.00,2026-02-24",
].join("\n");
test("parseMoneyToCents reads dollars and cents", () => {
    assert(parseMoneyToCents("40000.00") === 4000000, "40000.00 is 4000000 cents");
    assert(parseMoneyToCents("6005") === 600500, "whole dollars allowed");
    assert(parseMoneyToCents("12450.5") === 1245050, "one decimal place allowed");
});
test("parseMoneyToCents rejects a negative or junk amount", () => {
    let threw = 0;
    for (const bad of ["-1.00", "abc", "10.999"]) {
        try {
            parseMoneyToCents(bad);
        }
        catch {
            threw += 1;
        }
    }
    assert(threw === 3, "all three bad amounts should throw");
});
test("isValidDate accepts a real date and rejects a fake one", () => {
    assert(isValidDate("2026-01-15"), "real date");
    assert(!isValidDate("2026-02-30"), "Feb 30 is not real");
    assert(!isValidDate("2026-1-15"), "must be zero-padded");
});
test("duplicate, missing-field rows are skipped with warnings", () => {
    const { lines, warnings } = parseSpendCsv(SAMPLE);
    assert(lines.length === 12, "twelve clean lines kept");
    const skipped = warnings.filter((w) => w.kind === "skipped");
    assert(skipped.length === 2, "two rows skipped: the duplicate L001 and the supplier-less L012");
    assert(skipped.some((w) => w.message.includes("repeats")), "duplicate line id is named");
    assert(skipped.some((w) => w.lineId === "L012"), "the supplier-less line is named");
});
test("an unrecognized category is kept but flagged", () => {
    const { lines, warnings } = parseSpendCsv(SAMPLE);
    const flagged = warnings.filter((w) => w.kind === "flagged");
    assert(flagged.length === 1, "one flagged line");
    assert(flagged[0].lineId === "L013", "L013 carries the unknown category");
    const l013 = lines.find((l) => l.lineId === "L013");
    assert(!l013.categoryKnown, "L013 category is marked not known");
});
test("a blank contract id reads as off-contract", () => {
    const { lines } = parseSpendCsv(SAMPLE);
    const l006 = lines.find((l) => l.lineId === "L006");
    assert(!l006.onContract, "L006 has no contract");
    assert(l006.contractId === "", "off-contract lines carry an empty contract id");
    const l001 = lines.find((l) => l.lineId === "L001");
    assert(l001.onContract && l001.contractId === "C-1001", "L001 keeps its contract");
});
test("worked example: total spend is 135955.00", () => {
    const { lines, warnings } = parseSpendCsv(SAMPLE);
    const summary = summarize(lines, warnings);
    assert(summary.totalCents === 13595500, "total 135955.00");
    assert(summary.supplierCount === 5, "five suppliers");
    assert(summary.flaggedCount === 1, "one flagged line");
});
test("on- and off-contract spend split to 125955.00 and 10000.00", () => {
    const { lines, warnings } = parseSpendCsv(SAMPLE);
    const summary = summarize(lines, warnings);
    assert(summary.offContractCents === 1000000, "off-contract 10000.00 (L006 8000 + L009 2000)");
    assert(summary.onContractCents === 12595500, "on-contract 125955.00");
});
test("worked example: Northwind Supply leads at 65000.00 and 47.81 percent", () => {
    const { lines } = parseSpendCsv(SAMPLE);
    const suppliers = totalsBySupplier(lines);
    assert(suppliers[0].supplier === "Northwind Supply", "Northwind is first");
    assert(suppliers[0].cents === 6500000, "Northwind totals 65000.00");
    assert(suppliers[0].pct === 47.81, "Northwind is 47.81 percent of spend");
    assert(suppliers[4].supplier === "Harbour Freight Co", "Harbour Freight is last");
    assert(suppliers[4].cents === 200000, "Harbour Freight totals 2000.00");
});
test("category totals reconcile to the spend total", () => {
    const { lines } = parseSpendCsv(SAMPLE);
    const categories = totalsByCategory(lines);
    const sum = categories.reduce((s, c) => s + c.cents, 0);
    assert(sum === 13595500, "category totals sum to 135955.00");
    assert(categories[0].category === "IT Hardware" && categories[0].cents === 6500000, "IT Hardware leads at 65000.00");
    const stationery = categories.find((c) => c.category === "Stationery");
    assert(!stationery.known && stationery.cents === 150000, "the flagged Stationery bucket holds 1500.00");
});
test("normalized CSV is ready for the other two views", () => {
    const { lines } = parseSpendCsv(SAMPLE);
    const rows = toNormalizedCsv(lines).split("\n");
    assert(rows[0] === "line_id,supplier,category,contract_id,on_contract,po_amount,received_amount,invoice_amount,invoice_date", "header");
    assert(rows[1] === "L001,Northwind Supply,IT Hardware,C-1001,Y,40000.00,40000.00,40000.00,2026-01-15", "first clean line");
    assert(rows.length === 13, "header plus twelve clean lines");
    const l006 = rows.find((r) => r.startsWith("L006,"));
    assert(l006.split(",")[4] === "N", "L006 exports as off-contract");
});
test("a malformed amount rejects the whole file", () => {
    let message = "";
    try {
        parseSpendCsv("line_id,supplier,category,contract_id,po_amount,received_amount,invoice_amount,invoice_date\nL001,Northwind Supply,IT Hardware,C-1001,oops,40000.00,40000.00,2026-01-15");
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("dollar figure"), "a non-numeric amount should be named");
});
test("a bad header rejects the whole file", () => {
    let threw = false;
    try {
        parseSpendCsv("id,vendor,cat,contract,po,recv,inv,date\nL001,x,y,z,1,1,1,2026-01-15");
    }
    catch {
        threw = true;
    }
    assert(threw, "bad header should throw");
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
