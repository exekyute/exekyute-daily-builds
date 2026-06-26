"use strict";
/*
 * Pure 13-week liquidity-forecast logic.
 *
 * No DOM access and no I/O. Every function takes inputs and returns values, so
 * the test harness can import this file directly and assert on the numbers.
 *
 * The job is a rolling 13-week cash forecast: start from opening cash, then for
 * each week add projected inflows, subtract projected operating outflows and any
 * debt coming due, carry the closing balance forward, and flag any week that
 * ends below a minimum-cash buffer. Opening cash comes from the Cash Position
 * Dashboard and debt maturities come from the Maturity Ladder. All amounts are
 * Canadian dollars held in integer cents. Every rule is in spec.md.
 */
const WEEKS = 13;
/** Format integer cents as a fixed dollar string, e.g. 59125050 -> "591250.50". */
function centsToFixed(cents) {
    const sign = cents < 0 ? "-" : "";
    const abs = Math.abs(cents);
    return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}
/** Parse a money string into integer cents. Negatives allowed only when asked. */
function parseMoneyToCents(raw, allowNegative) {
    const text = raw.trim();
    if (!/^-?\d+(\.\d{1,2})?$/.test(text)) {
        throw new Error(`"${raw}" is not a valid dollar amount.`);
    }
    const negative = text.startsWith("-");
    if (negative && !allowNegative) {
        throw new Error(`"${raw}" must not be negative.`);
    }
    const unsigned = negative ? text.slice(1) : text;
    const [whole, frac = ""] = unsigned.split(".");
    const cents = Number(whole) * 100 + Number(frac.padEnd(2, "0"));
    return negative ? -cents : cents;
}
/**
 * Sum the closing_balance column of a closing-balances.csv from the Cash
 * Position Dashboard. The total is the opening cash for the forecast. Balances
 * may be negative.
 *
 * Expected header: account,closing_balance
 */
function sumClosingBalancesCsv(text) {
    const lines = text
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
    if (lines.length === 0) {
        throw new Error("The closing-balances file is empty.");
    }
    const header = lines[0].toLowerCase().replace(/\s+/g, "");
    if (header !== "account,closing_balance") {
        throw new Error('Unexpected header. The closing-balances file must start with "account,closing_balance".');
    }
    let total = 0;
    for (let i = 1; i < lines.length; i++) {
        const cells = lines[i].split(",").map((c) => c.trim());
        if (cells.length !== 2) {
            throw new Error(`Closing-balances row ${i + 1} has ${cells.length} fields, expected 2.`);
        }
        total += parseMoneyToCents(cells[1], true);
    }
    return total;
}
/**
 * Parse and validate the operating-cashflows CSV. Requires weeks 1 through 13,
 * each present exactly once. Throws a clear, row-numbered message on the first
 * problem it finds.
 *
 * Expected header: week,label,operating_inflows,operating_outflows
 */
function parseOperatingCsv(text) {
    const lines = text
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
    if (lines.length === 0) {
        throw new Error("The file is empty.");
    }
    const header = lines[0].toLowerCase().replace(/\s+/g, "");
    if (header !== "week,label,operating_inflows,operating_outflows") {
        throw new Error('Unexpected header. The first row must be exactly "week,label,operating_inflows,operating_outflows".');
    }
    const byWeek = new Map();
    for (let i = 1; i < lines.length; i++) {
        const rowNumber = i + 1;
        const cells = lines[i].split(",").map((c) => c.trim());
        if (cells.length !== 4) {
            throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 4.`);
        }
        const [weekRaw, label, inRaw, outRaw] = cells;
        const week = Number(weekRaw);
        if (!Number.isInteger(week) || week < 1 || week > WEEKS) {
            throw new Error(`Row ${rowNumber}: week "${weekRaw}" must be a whole number from 1 to ${WEEKS}.`);
        }
        if (byWeek.has(week)) {
            throw new Error(`Row ${rowNumber}: week ${week} appears more than once.`);
        }
        if (label.length === 0) {
            throw new Error(`Row ${rowNumber}: label is blank.`);
        }
        let inflow;
        let outflow;
        try {
            inflow = parseMoneyToCents(inRaw, false);
        }
        catch {
            throw new Error(`Row ${rowNumber}: operating_inflows "${inRaw}" must be a dollar figure of zero or more.`);
        }
        try {
            outflow = parseMoneyToCents(outRaw, false);
        }
        catch {
            throw new Error(`Row ${rowNumber}: operating_outflows "${outRaw}" must be a dollar figure of zero or more.`);
        }
        byWeek.set(week, { week, label, operatingInflowCents: inflow, operatingOutflowCents: outflow });
    }
    const flows = [];
    for (let w = 1; w <= WEEKS; w++) {
        const flow = byWeek.get(w);
        if (!flow) {
            throw new Error(`The file is missing week ${w}. Weeks 1 to ${WEEKS} must all be present.`);
        }
        flows.push(flow);
    }
    return flows;
}
/**
 * Parse a maturities-by-week.csv from the Maturity Ladder into a per-week debt
 * map. Any week 1..13 may appear, each at most once; weeks left out are zero.
 *
 * Expected header: week,debt_due
 */
function parseMaturitiesCsv(text) {
    const lines = text
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
    if (lines.length === 0) {
        throw new Error("The maturities file is empty.");
    }
    const header = lines[0].toLowerCase().replace(/\s+/g, "");
    if (header !== "week,debt_due") {
        throw new Error('Unexpected header. The maturities file must start with "week,debt_due".');
    }
    const byWeek = new Map();
    for (let i = 1; i < lines.length; i++) {
        const rowNumber = i + 1;
        const cells = lines[i].split(",").map((c) => c.trim());
        if (cells.length !== 2) {
            throw new Error(`Maturities row ${rowNumber} has ${cells.length} fields, expected 2.`);
        }
        const week = Number(cells[0]);
        if (!Number.isInteger(week) || week < 1 || week > WEEKS) {
            throw new Error(`Maturities row ${rowNumber}: week "${cells[0]}" must be a whole number from 1 to ${WEEKS}.`);
        }
        if (byWeek.has(week)) {
            throw new Error(`Maturities row ${rowNumber}: week ${week} appears more than once.`);
        }
        byWeek.set(week, parseMoneyToCents(cells[1], false));
    }
    return byWeek;
}
/**
 * Run the forecast. Opening cash starts week 1; each week's closing carries into
 * the next week's opening. A week ending below the buffer is a breach.
 */
function runForecast(flows, debtByWeek, config) {
    var _a;
    const results = [];
    let opening = config.openingCashCents;
    for (const flow of flows) {
        const debtDue = (_a = debtByWeek.get(flow.week)) !== null && _a !== void 0 ? _a : 0;
        const totalOutflow = flow.operatingOutflowCents + debtDue;
        const net = flow.operatingInflowCents - totalOutflow;
        const closing = opening + net;
        const headroom = closing - config.minimumBufferCents;
        results.push({
            week: flow.week,
            label: flow.label,
            openingCents: opening,
            inflowCents: flow.operatingInflowCents,
            operatingOutflowCents: flow.operatingOutflowCents,
            debtDueCents: debtDue,
            totalOutflowCents: totalOutflow,
            netCents: net,
            closingCents: closing,
            headroomCents: headroom,
            breach: closing < config.minimumBufferCents,
        });
        opening = closing;
    }
    return results;
}
/** Roll the weekly results up into the headline numbers shown above the chart. */
function summarize(results) {
    let lowest = results[0];
    let firstBreach = 0;
    let breachCount = 0;
    for (const r of results) {
        if (r.closingCents < lowest.closingCents) {
            lowest = r;
        }
        if (r.breach) {
            breachCount += 1;
            if (firstBreach === 0) {
                firstBreach = r.week;
            }
        }
    }
    return {
        weeks: results.length,
        endingCashCents: results[results.length - 1].closingCents,
        lowestClosingCents: lowest.closingCents,
        lowestWeek: lowest.week,
        breachCount,
        firstBreachWeek: firstBreach,
    };
}
/** Render the projection as a CSV for a record or a downstream report. */
function toForecastCsv(results) {
    const header = "week,label,opening,inflows,operating_outflows,debt_due,total_outflows,net,closing,breach";
    const body = results.map((r) => [
        r.week,
        r.label,
        centsToFixed(r.openingCents),
        centsToFixed(r.inflowCents),
        centsToFixed(r.operatingOutflowCents),
        centsToFixed(r.debtDueCents),
        centsToFixed(r.totalOutflowCents),
        centsToFixed(r.netCents),
        centsToFixed(r.closingCents),
        r.breach ? "breach" : "ok",
    ].join(","));
    return [header, ...body].join("\n");
}
