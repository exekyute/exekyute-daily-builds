"use strict";
/*
 * Pure logic for the PO/Invoice Compliance view.
 *
 * No DOM access and no I/O. Every function takes inputs and returns values, so
 * the test harness can load this file directly and assert on the numbers.
 *
 * The job is purchase-to-pay compliance. Read the normalized spend file the
 * Spend Analysis Dashboard writes and flag two things on each line: spend that
 * runs outside a contract, and three-way-match exceptions where the purchase
 * order, the goods receipt, and the invoice do not agree within tolerance. All
 * amounts are Canadian dollars and money is held in integer cents so the checks
 * are exact. Every rule is written out in spec.md.
 */
// A line passes the three-way match when the purchase order, receipt, and
// invoice agree within this tolerance: the greater of 5.00 dollars or 1 percent
// of the purchase-order amount.
const TOLERANCE_FLOOR_CENTS = 500;
const TOLERANCE_RATE = 0.01;
/** Format integer cents as a plain dollar string. */
function centsToFixed(cents) {
    const sign = cents < 0 ? "-" : "";
    const abs = Math.abs(cents);
    const dollars = Math.floor(abs / 100);
    const rest = abs % 100;
    return `${sign}${dollars}.${String(rest).padStart(2, "0")}`;
}
/** Parse a money string into integer cents. Zero or more, at most two decimals. */
function parseMoneyToCents(raw) {
    const text = raw.trim();
    if (!/^\d+(\.\d{1,2})?$/.test(text)) {
        throw new Error(`"${raw}" is not a valid dollar amount of zero or more.`);
    }
    const [whole, frac = ""] = text.split(".");
    return Number(whole) * 100 + Number(frac.padEnd(2, "0"));
}
/** Half-up percentage to two decimals. */
function pctOf(part, whole) {
    if (whole === 0) {
        return 0;
    }
    return Math.round((part / whole) * 10000) / 100;
}
/** The match tolerance for a line: the greater of 5.00 or 1 percent of the PO. */
function toleranceFor(poCents) {
    return Math.max(TOLERANCE_FLOOR_CENTS, Math.round(poCents * TOLERANCE_RATE));
}
/**
 * Judge one line. A line is on-contract when its on_contract column is Y. It
 * passes the three-way match when the purchase order, receipt, and invoice all
 * sit within tolerance of one another. Each breach adds a plain-language reason.
 */
function judgeLine(input) {
    const tol = toleranceFor(input.poCents);
    const reasons = [];
    if (!input.onContract) {
        reasons.push("off-contract spend");
    }
    if (input.invoiceCents - input.poCents > tol) {
        reasons.push(`invoice exceeds PO by ${centsToFixed(input.invoiceCents - input.poCents)}`);
    }
    else if (input.poCents - input.invoiceCents > tol) {
        reasons.push(`invoice under PO by ${centsToFixed(input.poCents - input.invoiceCents)}`);
    }
    if (input.invoiceCents - input.receivedCents > tol) {
        reasons.push(`invoice exceeds receipt by ${centsToFixed(input.invoiceCents - input.receivedCents)}`);
    }
    if (input.poCents - input.receivedCents > tol) {
        reasons.push(`receipt short of PO by ${centsToFixed(input.poCents - input.receivedCents)}`);
    }
    const maxDiff = Math.max(Math.abs(input.poCents - input.invoiceCents), Math.abs(input.invoiceCents - input.receivedCents), Math.abs(input.poCents - input.receivedCents));
    const matched = maxDiff <= tol;
    return {
        lineId: input.lineId,
        supplier: input.supplier,
        category: input.category,
        contractId: input.contractId,
        onContract: input.onContract,
        poCents: input.poCents,
        receivedCents: input.receivedCents,
        invoiceCents: input.invoiceCents,
        invoiceDate: input.invoiceDate,
        toleranceCents: tol,
        matched,
        offContract: !input.onContract,
        reasons,
    };
}
/**
 * Parse the normalized spend file the Spend Analysis Dashboard writes and judge
 * every line. A structural problem (wrong header, wrong field count, a
 * non-numeric amount) throws, because the file cannot be trusted.
 *
 * Expected header:
 * line_id,supplier,category,contract_id,on_contract,po_amount,received_amount,invoice_amount,invoice_date
 */
function parseAndJudge(text) {
    const rawLines = text
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
    if (rawLines.length === 0) {
        throw new Error("The file is empty.");
    }
    const header = rawLines[0].toLowerCase().replace(/\s+/g, "");
    const expected = "line_id,supplier,category,contract_id,on_contract,po_amount,received_amount,invoice_amount,invoice_date";
    if (header !== expected) {
        throw new Error("Unexpected header. This view reads the normalized-spend.csv the Spend Analysis Dashboard exports.");
    }
    const lines = [];
    for (let i = 1; i < rawLines.length; i++) {
        const rowNumber = i + 1;
        const cells = rawLines[i].split(",").map((cell) => cell.trim());
        if (cells.length !== 9) {
            throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 9.`);
        }
        const [lineId, supplier, category, contractId, onContractRaw, poRaw, receivedRaw, invoiceRaw, invoiceDate] = cells;
        const onContractFlag = onContractRaw.toUpperCase();
        if (onContractFlag !== "Y" && onContractFlag !== "N") {
            throw new Error(`Row ${rowNumber}: on_contract "${onContractRaw}" must be Y or N.`);
        }
        let poCents;
        let receivedCents;
        let invoiceCents;
        try {
            poCents = parseMoneyToCents(poRaw);
            receivedCents = parseMoneyToCents(receivedRaw);
            invoiceCents = parseMoneyToCents(invoiceRaw);
        }
        catch {
            throw new Error(`Row ${rowNumber}: po, received, and invoice amounts must each be a dollar figure of zero or more.`);
        }
        lines.push(judgeLine({
            lineId,
            supplier,
            category,
            contractId,
            onContract: onContractFlag === "Y",
            poCents,
            receivedCents,
            invoiceCents,
            invoiceDate,
        }));
    }
    if (lines.length === 0) {
        throw new Error("The file has a header but no spend lines.");
    }
    return lines;
}
/** Roll the judged lines into headline compliance figures. */
function summarize(lines) {
    const total = lines.length;
    const totalInvoiceCents = lines.reduce((s, l) => s + l.invoiceCents, 0);
    const offContract = lines.filter((l) => l.offContract);
    const exceptions = lines.filter((l) => !l.matched);
    const compliant = lines.filter((l) => l.onContract && l.matched);
    const flagged = lines.filter((l) => l.offContract || !l.matched);
    return {
        totalLines: total,
        totalInvoiceCents,
        compliantLines: compliant.length,
        compliantPct: pctOf(compliant.length, total),
        offContractLines: offContract.length,
        offContractCents: offContract.reduce((s, l) => s + l.invoiceCents, 0),
        exceptionLines: exceptions.length,
        exceptionCents: exceptions.reduce((s, l) => s + l.invoiceCents, 0),
        flaggedLines: flagged.length,
    };
}
/** Just the flagged lines, off-contract or match exceptions, in input order. */
function flaggedOnly(lines) {
    return lines.filter((l) => l.offContract || !l.matched);
}
