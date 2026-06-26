"use strict";
/*
 * Pure cohort retention logic.
 *
 * No DOM access and no I/O. Every function takes inputs and returns values, so
 * the test harness can import this file directly and assert on the numbers.
 *
 * The model groups customers by the month they signed up (their cohort), then
 * measures how much of each cohort is still there in the months that follow.
 * Retention can be read two ways: revenue retained against the cohort's starting
 * revenue, or active customers retained against the cohort's starting count. All
 * money is held in integer cents so the totals stay exact. The full rules are
 * written out in spec.md.
 */
const KNOWN_PLANS = ["Basic", "Pro", "Enterprise"];
/** Parse a positive money string with up to two decimals into exact cents. */
function parseMoneyToCents(raw, rowNumber, field) {
    if (!/^\d+(\.\d{1,2})?$/.test(raw)) {
        throw new Error(`Row ${rowNumber}: ${field} "${raw}" must be a positive amount with up to two decimals.`);
    }
    const [whole, frac = ""] = raw.split(".");
    const cents = Number(whole) * 100 + Number((frac + "00").slice(0, 2));
    if (cents <= 0) {
        throw new Error(`Row ${rowNumber}: ${field} "${raw}" must be greater than zero.`);
    }
    return cents;
}
/** True for a well-formed "YYYY-MM" string with a real month number. */
function isMonth(value) {
    if (!/^\d{4}-\d{2}$/.test(value)) {
        return false;
    }
    const month = Number(value.slice(5, 7));
    return month >= 1 && month <= 12;
}
/** Whole months from one "YYYY-MM" to another, e.g. 2025-01 to 2025-04 is 3. */
function monthsBetween(from, to) {
    const fy = Number(from.slice(0, 4));
    const fm = Number(from.slice(5, 7));
    const ty = Number(to.slice(0, 4));
    const tm = Number(to.slice(5, 7));
    return (ty - fy) * 12 + (tm - fm);
}
/** Add a whole number of months to a "YYYY-MM" string. */
function addMonths(month, count) {
    const y = Number(month.slice(0, 4));
    const m = Number(month.slice(5, 7));
    const zero = (y * 12 + (m - 1)) + count;
    const ny = Math.floor(zero / 12);
    const nm = (zero % 12) + 1;
    return `${ny}-${String(nm).padStart(2, "0")}`;
}
/** Round a ratio to a two-decimal percent, half up. */
function toPct(part, whole) {
    if (whole === 0) {
        return 0;
    }
    return Math.round((part / whole) * 10000) / 100;
}
/**
 * Parse and validate the ledger CSV. Throws an Error with a clear, row-numbered
 * message on the first problem it finds.
 *
 * Expected header: customer_id,plan,signup_month,month,mrr
 */
function parseLedgerCsv(text) {
    const lines = text
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
    if (lines.length === 0) {
        throw new Error("The file is empty.");
    }
    const header = lines[0].toLowerCase().replace(/\s+/g, "");
    if (header !== "customer_id,plan,signup_month,month,mrr") {
        throw new Error('Unexpected header. The first row must be exactly "customer_id,plan,signup_month,month,mrr".');
    }
    const seen = new Set(); // customer_id + month, to catch duplicates
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
        const rowNumber = i + 1; // 1-based, counting the header
        const cells = lines[i].split(",").map((cell) => cell.trim());
        if (cells.length !== 5) {
            throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 5.`);
        }
        const [customerId, plan, signupMonth, month, mrrRaw] = cells;
        if (customerId.length === 0) {
            throw new Error(`Row ${rowNumber}: customer_id is blank.`);
        }
        if (!KNOWN_PLANS.includes(plan)) {
            throw new Error(`Row ${rowNumber}: plan "${plan}" must be one of Basic, Pro, or Enterprise.`);
        }
        if (!isMonth(signupMonth)) {
            throw new Error(`Row ${rowNumber}: signup_month "${signupMonth}" is not a valid YYYY-MM month.`);
        }
        if (!isMonth(month)) {
            throw new Error(`Row ${rowNumber}: month "${month}" is not a valid YYYY-MM month.`);
        }
        if (monthsBetween(signupMonth, month) < 0) {
            throw new Error(`Row ${rowNumber}: month "${month}" is before signup_month "${signupMonth}".`);
        }
        const key = `${customerId}|${month}`;
        if (seen.has(key)) {
            throw new Error(`Row ${rowNumber}: customer "${customerId}" already has a row for ${month}.`);
        }
        seen.add(key);
        const mrrCents = parseMoneyToCents(mrrRaw, rowNumber, "mrr");
        rows.push({ customerId, plan, signupMonth, month, mrrCents });
    }
    if (rows.length === 0) {
        throw new Error("The file has a header but no data rows.");
    }
    return rows;
}
/** The latest month present in the ledger. */
function lastMonthIn(rows) {
    let last = rows[0].month;
    for (const row of rows) {
        if (row.month > last) {
            last = row.month;
        }
    }
    return last;
}
/** Distinct signup months in the ledger, ascending. */
function cohortsIn(rows) {
    const set = new Set();
    for (const row of rows) {
        set.add(row.signupMonth);
    }
    return Array.from(set).sort();
}
/**
 * Build one retention series per cohort. The widest cohort sets the number of
 * offset columns; cells past the end of the ledger for a given cohort are marked
 * with hasData false so the heatmap can leave them blank.
 */
function computeCohorts(rows) {
    const cohorts = cohortsIn(rows);
    const lastMonth = lastMonthIn(rows);
    const maxOffset = Math.max(0, ...cohorts.map((c) => monthsBetween(c, lastMonth)));
    return cohorts.map((cohort) => {
        const members = rows.filter((r) => r.signupMonth === cohort);
        const customerIds = new Set(members.map((r) => r.customerId));
        const cohortSize = customerIds.size;
        // Revenue and active count for each calendar month, restricted to this cohort.
        const startMonth = cohort;
        const startRows = members.filter((r) => r.month === startMonth);
        let startCents = 0;
        for (const r of startRows) {
            startCents += r.mrrCents;
        }
        const cells = [];
        for (let offset = 0; offset <= maxOffset; offset++) {
            const calendarMonth = addMonths(cohort, offset);
            const hasData = monthsBetween(cohort, lastMonth) >= offset;
            const monthRows = members.filter((r) => r.month === calendarMonth);
            let retainedCents = 0;
            for (const r of monthRows) {
                retainedCents += r.mrrCents;
            }
            const activeLogos = monthRows.length;
            cells.push({
                offset,
                hasData,
                retainedCents,
                activeLogos,
                revenuePct: toPct(retainedCents, startCents),
                logoPct: toPct(activeLogos, cohortSize),
            });
        }
        return { cohort, startCents, cohortSize, cells };
    });
}
/** Render the cohort table as a CSV, one row per cohort, revenue retention percents. */
function toCohortCsv(series) {
    const width = series.length === 0 ? 0 : series[0].cells.length;
    const offsets = Array.from({ length: width }, (_, i) => `month_${i}`);
    const header = ["cohort", "start_mrr", "cohort_size", ...offsets].join(",");
    const body = series.map((s) => {
        const start = (s.startCents / 100).toFixed(2);
        const pcts = s.cells.map((c) => (c.hasData ? c.revenuePct.toFixed(2) : ""));
        return [s.cohort, start, String(s.cohortSize), ...pcts].join(",");
    });
    return [header, ...body].join("\n");
}
