"use strict";
/*
 * Pure reserve-development logic.
 *
 * No DOM access and no I/O. Every function takes inputs and returns values, so
 * the test harness can import this file directly and assert on the numbers.
 *
 * The input is the clean-claims.csv the Claims Aging and Status Funnel writes.
 * This file pivots cumulative paid losses into a triangle, accident year down the
 * side and development month across the top, then reads the age-to-age
 * development factors off the overlapping diagonals, chains them into a factor to
 * ultimate for each development age, and projects each accident year's ultimate
 * paid and outstanding reserve. All money is held in integer cents so totals stay
 * exact. The full rules are in spec.md.
 */
const CLEAN_HEADER = "claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,incurred,earned_premium,is_latest,age_days,age_bucket,days_to_close";
/** Parse a money string with up to two decimals into exact cents. */
function parseMoneyToCents(raw, rowNumber, field) {
    if (!/^\d+(\.\d{1,2})?$/.test(raw)) {
        throw new Error(`Row ${rowNumber}: ${field} "${raw}" must be an amount with up to two decimals and no minus sign.`);
    }
    const [whole, frac = ""] = raw.split(".");
    return Number(whole) * 100 + Number((frac + "00").slice(0, 2));
}
/**
 * Parse and validate the clean-claims CSV. Throws an Error with a clear,
 * row-numbered message on the first problem it finds.
 */
function parseCleanCsv(text) {
    const lines = text
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
    if (lines.length === 0) {
        throw new Error("The file is empty.");
    }
    const header = lines[0].toLowerCase().replace(/\s+/g, "");
    if (header !== CLEAN_HEADER) {
        throw new Error("Unexpected header. This tool reads the clean-claims.csv exported by the Claims Aging and Status Funnel.");
    }
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
        const rowNumber = i + 1;
        const cells = lines[i].split(",").map((cell) => cell.trim());
        if (cells.length !== 16) {
            throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 16.`);
        }
        const line = cells[1];
        const accidentPeriod = cells[2];
        const devRaw = cells[5];
        const paidRaw = cells[8];
        if (line.length === 0) {
            throw new Error(`Row ${rowNumber}: line_of_business is blank.`);
        }
        if (!/^\d{4}$/.test(accidentPeriod)) {
            throw new Error(`Row ${rowNumber}: accident_period "${accidentPeriod}" must be a four-digit accident year.`);
        }
        if (!/^\d+$/.test(devRaw) || Number(devRaw) <= 0) {
            throw new Error(`Row ${rowNumber}: development_month "${devRaw}" must be a whole number of months greater than zero.`);
        }
        const paidCents = parseMoneyToCents(paidRaw, rowNumber, "paid_to_date");
        rows.push({ line, accidentPeriod, developmentMonth: Number(devRaw), paidCents });
    }
    if (rows.length === 0) {
        throw new Error("The file has a header but no data rows.");
    }
    return rows;
}
/** The distinct lines of business in the file, sorted, with "All" first. */
function linesIn(rows) {
    const set = new Set();
    for (const row of rows) {
        set.add(row.line);
    }
    return ["All", ...Array.from(set).sort()];
}
/** Round a positive cent amount to the nearest whole cent, halves up. */
function roundCents(value) {
    return Math.floor(value + 0.5);
}
/**
 * Build the cumulative-paid triangle for one line filter ("All" for the whole
 * book), then derive the age-to-age factors, the factors to ultimate, and each
 * accident year's projected ultimate and reserve.
 */
function buildTriangle(rows, lineFilter) {
    const scoped = lineFilter === "All" ? rows : rows.filter((r) => r.line === lineFilter);
    const periodSet = new Set();
    const devSet = new Set();
    const cells = new Map();
    for (const row of scoped) {
        periodSet.add(row.accidentPeriod);
        devSet.add(row.developmentMonth);
        const key = `${row.accidentPeriod}|${row.developmentMonth}`;
        cells.set(key, (cells.get(key) || 0) + row.paidCents);
    }
    const periods = Array.from(periodSet).sort();
    const devMonths = Array.from(devSet).sort((a, b) => a - b);
    // Age-to-age factor for each adjacent pair: sum of cumulative paid at the later
    // age over the sum at the earlier age, across the accident years that have both.
    const ageToAge = [];
    for (let d = 0; d < devMonths.length - 1; d++) {
        const from = devMonths[d];
        const to = devMonths[d + 1];
        let sumFrom = 0;
        let sumTo = 0;
        for (const period of periods) {
            const a = cells.get(`${period}|${from}`);
            const b = cells.get(`${period}|${to}`);
            if (a !== undefined && b !== undefined) {
                sumFrom += a;
                sumTo += b;
            }
        }
        ageToAge.push({ from, to, factor: sumFrom === 0 ? 1 : sumTo / sumFrom });
    }
    // Factor to ultimate from each development age is the product of every later
    // age-to-age factor. The most mature age develops to ultimate by a factor of 1.
    const cdf = new Map();
    for (let d = 0; d < devMonths.length; d++) {
        let product = 1;
        for (let k = d; k < ageToAge.length; k++) {
            product *= ageToAge[k].factor;
        }
        cdf.set(devMonths[d], product);
    }
    // Project each accident year from its most mature cumulative paid.
    const projections = periods.map((period) => {
        let latestDev = -1;
        let latestPaidCents = 0;
        for (const dev of devMonths) {
            const v = cells.get(`${period}|${dev}`);
            if (v !== undefined && dev > latestDev) {
                latestDev = dev;
                latestPaidCents = v;
            }
        }
        const factor = cdf.get(latestDev);
        const ultimateCents = roundCents(latestPaidCents * factor);
        return { period, latestDev, latestPaidCents, cdf: factor, ultimateCents, reserveCents: ultimateCents - latestPaidCents };
    });
    return { lineFilter, periods, devMonths, cells, ageToAge, cdf, projections };
}
