"use strict";
/*
 * Test harness for the cash-position logic. Loads positions.js, runs assertions,
 * and prints PASS or FAIL on the page. Open tests.html to see it run.
 *
 * The headline case is the worked example in spec.md: the CAD-OPS account opens
 * at 250000.00, takes in 97500.50, pays out 184000.00, and closes at 163500.50.
 * Across the four sample accounts the closing positions sum to 648000.50, which
 * is the opening cash the Liquidity Forecast reads.
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
    "date,account,direction,amount,description",
    "2026-06-15,CAD-OPS,opening,250000.00,Opening balance",
    "2026-06-15,CAD-OPS,in,82000.00,Customer receipts",
    "2026-06-15,CAD-OPS,in,15500.50,Interest credit",
    "2026-06-15,CAD-OPS,out,64000.00,Supplier run",
    "2026-06-15,CAD-OPS,out,120000.00,Payroll transfer",
    "2026-06-15,CAD-PAYROLL,opening,40000.00,Opening balance",
    "2026-06-15,CAD-PAYROLL,out,38500.00,Payroll funding",
    "2026-06-15,CAD-TAX,opening,5000.00,Opening balance",
    "2026-06-15,CAD-TAX,out,22000.00,HST remittance",
    "2026-06-15,CAD-RESERVE,opening,500000.00,Opening balance",
].join("\n");
test("parseMoneyToCents reads dollars and cents", () => {
    assert(parseMoneyToCents("250000.00", false) === 25000000, "250000.00 is 25000000 cents");
    assert(parseMoneyToCents("15500.5", false) === 1550050, "15500.5 is 1550050 cents");
    assert(parseMoneyToCents("-17000.00", true) === -1700000, "negative allowed when permitted");
});
test("parseMoneyToCents rejects a negative when not allowed", () => {
    let threw = false;
    try {
        parseMoneyToCents("-1.00", false);
    }
    catch {
        threw = true;
    }
    assert(threw, "negative amount should throw");
});
test("centsToFixed round-trips through two decimals", () => {
    assert(centsToFixed(16350050) === "163500.50", "positive");
    assert(centsToFixed(-1700000) === "-17000.00", "negative");
    assert(centsToFixed(150000) === "1500.00", "even dollars");
});
test("isValidDate accepts a real date and rejects a fake one", () => {
    assert(isValidDate("2026-06-15"), "real date");
    assert(!isValidDate("2026-02-30"), "Feb 30 is not real");
    assert(!isValidDate("2026-6-15"), "must be zero-padded");
});
test("worked example: CAD-OPS closes at 163500.50", () => {
    const positions = computePositions(parsePositionCsv(SAMPLE));
    const ops = positions.find((p) => p.account === "CAD-OPS");
    assert(ops.openingCents === 25000000, "opening 250000.00");
    assert(ops.inflowCents === 9750050, "inflows 97500.50");
    assert(ops.outflowCents === 18400000, "outflows 184000.00");
    assert(ops.closingCents === 16350050, "closing 163500.50");
});
test("an account that pays out past its balance is flagged overdrawn", () => {
    const positions = computePositions(parsePositionCsv(SAMPLE));
    const tax = positions.find((p) => p.account === "CAD-TAX");
    assert(tax.closingCents === -1700000, "CAD-TAX closes at -17000.00");
    assert(tax.overdrawn, "CAD-TAX is overdrawn");
});
test("a zero-activity account carries its opening to close", () => {
    const positions = computePositions(parsePositionCsv(SAMPLE));
    const reserve = positions.find((p) => p.account === "CAD-RESERVE");
    assert(reserve.inflowCents === 0 && reserve.outflowCents === 0, "no activity");
    assert(reserve.closingCents === 50000000, "closing equals opening 500000.00");
});
test("consolidated closing across the sample is 648000.50", () => {
    const movements = parsePositionCsv(SAMPLE);
    const summary = summarize(computePositions(movements), movements);
    assert(summary.accounts === 4, "four accounts");
    assert(summary.closingCents === 64800050, "total closing 648000.50");
    assert(summary.overdrawnCount === 1, "one overdrawn account");
});
test("CSV parser rejects a bad header", () => {
    let threw = false;
    try {
        parsePositionCsv("day,acct,dir,amt,note\n2026-06-15,CAD-OPS,opening,1.00,x");
    }
    catch {
        threw = true;
    }
    assert(threw, "bad header should throw");
});
test("a second opening row for one account is rejected", () => {
    let message = "";
    try {
        computePositions(parsePositionCsv("date,account,direction,amount,description\n2026-06-15,CAD-OPS,opening,1.00,a\n2026-06-15,CAD-OPS,opening,2.00,b"));
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("more than one opening"), "double opening should be named");
});
test("an account with no opening row is rejected", () => {
    let message = "";
    try {
        computePositions(parsePositionCsv("date,account,direction,amount,description\n2026-06-15,CAD-OPS,in,1.00,a"));
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("missing an opening"), "missing opening should be named");
});
test("an exact duplicate row is rejected", () => {
    let message = "";
    try {
        parsePositionCsv("date,account,direction,amount,description\n2026-06-15,CAD-OPS,opening,1.00,a\n2026-06-15,CAD-OPS,opening,1.00,a");
    }
    catch (err) {
        message = err instanceof Error ? err.message : "";
    }
    assert(message.includes("duplicate"), "duplicate row should be named");
});
test("closing-balances CSV is sorted and to the cent", () => {
    const csv = toClosingBalancesCsv(computePositions(parsePositionCsv(SAMPLE)));
    const rows = csv.split("\n");
    assert(rows[0] === "account,closing_balance", "header");
    assert(rows[1] === "CAD-OPS,163500.50", "first account closing");
    assert(rows[3] === "CAD-RESERVE,500000.00", "reserve closing");
    assert(rows[4] === "CAD-TAX,-17000.00", "overdrawn closing keeps its sign");
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
