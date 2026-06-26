"use strict";
/*
 * Pure dashboard logic for the 311 operations view.
 *
 * No DOM access and no I/O. Every function takes inputs and returns values, so the
 * test harness can import this file directly and assert on the numbers. The dashboard
 * reads three CSVs written by the SQL tools: the period summary (backlog and flow),
 * the open-request aging buckets, and the time-to-close figures by category.
 *
 * Money is held in integer cents, the same as the SQL runner, so the totals shown
 * here match it to the cent. The full rules live in spec.md.
 */
/** Split CSV text into trimmed rows of cells. Blank lines are dropped. The data
 *  these tools write has no quoted fields, so a plain split is enough. */
function splitCsv(text) {
    return text
        .replace(/\r\n/g, "\n")
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.length > 0)
        .map((line) => line.split(",").map((cell) => cell.trim()));
}
/** Identify a file by the columns in its header, so the loader never mislabels one. */
function detectKind(header) {
    const cols = header.map((c) => c.toLowerCase());
    if (cols.indexOf("cost_to_serve_cents") !== -1) {
        return "period";
    }
    if (cols.indexOf("open_count") !== -1 && cols.indexOf("bucket") !== -1) {
        return "aging";
    }
    if (cols.indexOf("total_days") !== -1 && cols.indexOf("category") !== -1) {
        return "category";
    }
    return "unknown";
}
function columnIndex(header, name) {
    const idx = header.map((c) => c.toLowerCase()).indexOf(name);
    if (idx === -1) {
        throw new Error("Missing column: " + name);
    }
    return idx;
}
function toInt(value, label) {
    if (!/^-?\d+$/.test(value)) {
        throw new Error("Expected a whole number for " + label + ", found: " + JSON.stringify(value));
    }
    return parseInt(value, 10);
}
function parsePeriodRows(table) {
    const header = table[0];
    const iPeriod = columnIndex(header, "period");
    const iDept = columnIndex(header, "department");
    const iOpen = columnIndex(header, "opening");
    const iNew = columnIndex(header, "new_requests");
    const iClosed = columnIndex(header, "closed");
    const iClosing = columnIndex(header, "closing");
    const iCost = columnIndex(header, "cost_to_serve_cents");
    const rows = [];
    for (let r = 1; r < table.length; r++) {
        const cells = table[r];
        rows.push({
            period: cells[iPeriod],
            department: cells[iDept],
            opening: toInt(cells[iOpen], "opening"),
            newRequests: toInt(cells[iNew], "new_requests"),
            closed: toInt(cells[iClosed], "closed"),
            closing: toInt(cells[iClosing], "closing"),
            costToServeCents: toInt(cells[iCost], "cost_to_serve_cents"),
        });
    }
    return rows;
}
function parseAgingRows(table) {
    const header = table[0];
    const iBucket = columnIndex(header, "bucket");
    const iOpen = columnIndex(header, "open_count");
    const iOverdue = columnIndex(header, "overdue");
    const rows = [];
    for (let r = 1; r < table.length; r++) {
        const cells = table[r];
        rows.push({
            bucket: cells[iBucket],
            openCount: toInt(cells[iOpen], "open_count"),
            overdue: toInt(cells[iOverdue], "overdue"),
        });
    }
    return rows;
}
function parseCategoryRows(table) {
    const header = table[0];
    const iCat = columnIndex(header, "category");
    const iClosed = columnIndex(header, "closed_count");
    const iDays = columnIndex(header, "total_days");
    const iTarget = columnIndex(header, "target_days");
    const iBreach = columnIndex(header, "breaches");
    const rows = [];
    for (let r = 1; r < table.length; r++) {
        const cells = table[r];
        rows.push({
            category: cells[iCat],
            closedCount: toInt(cells[iClosed], "closed_count"),
            totalDays: toInt(cells[iDays], "total_days"),
            targetDays: toInt(cells[iTarget], "target_days"),
            breaches: toInt(cells[iBreach], "breaches"),
        });
    }
    return rows;
}
/** The flow identity for one row: opening + new - closed should equal closing. */
function identityHolds(row) {
    return row.opening + row.newRequests - row.closed === row.closing;
}
function identityFailures(rows) {
    return rows.filter((row) => !identityHolds(row));
}
function totalCostCents(rows) {
    return rows.reduce((sum, row) => sum + row.costToServeCents, 0);
}
function totalOpen(rows) {
    return rows.reduce((sum, row) => sum + row.openCount, 0);
}
function totalOverdue(rows) {
    return rows.reduce((sum, row) => sum + row.overdue, 0);
}
function totalClosed(rows) {
    return rows.reduce((sum, row) => sum + row.closedCount, 0);
}
function totalBreaches(rows) {
    return rows.reduce((sum, row) => sum + row.breaches, 0);
}
/** Round a non-negative number to the nearest integer, halves up. */
function roundHalfUp(value) {
    return Math.floor(value + 0.5);
}
/** Average days expressed in hundredths, e.g. 11.22 days returns 1122. Working in
 *  hundredths keeps the rounding identical to the runner's Decimal rounding. */
function avgDaysHundredths(totalDaysValue, count) {
    if (count === 0) {
        return 0;
    }
    return roundHalfUp((totalDaysValue * 100) / count);
}
/** Format a hundredths value as a two-decimal string, e.g. 1122 returns "11.22". */
function formatHundredths(hundredths) {
    const whole = Math.floor(hundredths / 100);
    const frac = hundredths % 100;
    return whole + "." + (frac < 10 ? "0" + frac : String(frac));
}
function overallAvgDaysHundredths(rows) {
    const days = rows.reduce((sum, row) => sum + row.totalDays, 0);
    return avgDaysHundredths(days, totalClosed(rows));
}
const CAD = typeof Intl !== "undefined"
    ? new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD" })
    : null;
/** Format integer cents as Canadian dollars, e.g. 70850 returns "$708.50". */
function formatCadFromCents(cents) {
    if (CAD) {
        return CAD.format(cents / 100);
    }
    const whole = Math.floor(cents / 100);
    const frac = cents % 100;
    return "$" + whole + "." + (frac < 10 ? "0" + frac : String(frac));
}
