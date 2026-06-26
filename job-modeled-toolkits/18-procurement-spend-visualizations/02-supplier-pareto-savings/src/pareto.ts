/*
 * Pure logic for the Supplier Pareto and Savings Tracker.
 *
 * No DOM access and no I/O. Every function takes inputs and returns values, so
 * the test harness can load this file directly and assert on the numbers.
 *
 * Two jobs share this view. The Pareto reads the normalized spend file the
 * Spend Analysis Dashboard writes, ranks suppliers by spend, and marks the
 * "vital few" that make up the first 80 percent of spend. The Savings Tracker
 * reads a list of savings initiatives and compares realized savings against
 * target. All amounts are Canadian dollars and money is held in integer cents
 * so totals are exact. Every rule is written out in spec.md.
 */

// The Pareto cut. Suppliers are marked vital few up to and including the first
// one whose running share reaches this percentage of total spend.
const PARETO_THRESHOLD = 80;

interface SupplierSpend {
  supplier: string;
  cents: number;
  pct: number; // share of total spend
  cumulativeCents: number;
  cumulativePct: number;
  vitalFew: boolean;
}

interface ParetoResult {
  rows: SupplierSpend[];
  totalCents: number;
  supplierCount: number;
  vitalFewCount: number;
  vitalFewCents: number;
  vitalFewPct: number; // share of spend the vital few make up
}

interface Initiative {
  id: string;
  category: string;
  baselineCents: number;
  currentCents: number;
  targetCents: number;
  realizedCents: number; // baseline minus current, may be negative on an overrun
  attainmentPct: number | null; // realized over target, null when no target is set
  met: boolean; // realized reaches or beats target
}

interface Warning {
  id: string;
  message: string;
}

interface SavingsResult {
  rows: Initiative[];
  warnings: Warning[];
  totalTargetCents: number;
  totalRealizedCents: number;
  overallAttainmentPct: number | null;
}

/** Format integer cents as a plain dollar string, e.g. -60000 -> "-600.00". */
function centsToFixed(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const dollars = Math.floor(abs / 100);
  const rest = abs % 100;
  return `${sign}${dollars}.${String(rest).padStart(2, "0")}`;
}

/** Parse a money string into integer cents. Zero or more, at most two decimals. */
function parseMoneyToCents(raw: string): number {
  const text = raw.trim();
  if (!/^\d+(\.\d{1,2})?$/.test(text)) {
    throw new Error(`"${raw}" is not a valid dollar amount of zero or more.`);
  }
  const [whole, frac = ""] = text.split(".");
  return Number(whole) * 100 + Number(frac.padEnd(2, "0"));
}

/** Half-up percentage to two decimals. Signed, so an overrun reads negative. */
function signedPct(part: number, whole: number): number {
  return Math.round((part / whole) * 10000) / 100;
}

/**
 * Parse the normalized spend file the Spend Analysis Dashboard writes and total
 * the invoice amount by supplier. A structural problem (wrong header, wrong
 * field count, a non-numeric amount) throws, because the file cannot be trusted.
 *
 * Expected header:
 * line_id,supplier,category,contract_id,on_contract,po_amount,received_amount,invoice_amount,invoice_date
 */
function parseNormalizedCsv(text: string): Map<string, number> {
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

  const bySupplier = new Map<string, number>();
  for (let i = 1; i < rawLines.length; i++) {
    const rowNumber = i + 1;
    const cells = rawLines[i].split(",").map((cell) => cell.trim());
    if (cells.length !== 9) {
      throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 9.`);
    }
    const supplier = cells[1];
    if (supplier === "") {
      throw new Error(`Row ${rowNumber} has no supplier.`);
    }
    let invoiceCents: number;
    try {
      invoiceCents = parseMoneyToCents(cells[7]);
    } catch {
      throw new Error(`Row ${rowNumber}: invoice_amount "${cells[7]}" is not a valid dollar amount.`);
    }
    bySupplier.set(supplier, (bySupplier.get(supplier) || 0) + invoiceCents);
  }

  if (bySupplier.size === 0) {
    throw new Error("The file has a header but no spend lines.");
  }
  return bySupplier;
}

/**
 * Rank suppliers by spend, compute running totals and shares, and mark the vital
 * few. Suppliers are sorted by spend descending then by name. The vital few are
 * every supplier from the top up to and including the first whose cumulative
 * share reaches the Pareto threshold.
 */
function buildPareto(bySupplier: Map<string, number>): ParetoResult {
  const entries: { supplier: string; cents: number }[] = [];
  bySupplier.forEach((cents, supplier) => entries.push({ supplier, cents }));
  entries.sort((a, b) => (b.cents - a.cents) || (a.supplier < b.supplier ? -1 : 1));

  const total = entries.reduce((s, e) => s + e.cents, 0);
  const rows: SupplierSpend[] = [];
  let running = 0;
  let crossed = false;
  for (const e of entries) {
    running += e.cents;
    const cumulativePct = total === 0 ? 0 : signedPct(running, total);
    // This supplier is vital few if the cut has not been reached yet. The one
    // that reaches it is included, then the flag stops.
    const vitalFew = !crossed;
    if (cumulativePct >= PARETO_THRESHOLD) {
      crossed = true;
    }
    rows.push({
      supplier: e.supplier,
      cents: e.cents,
      pct: total === 0 ? 0 : signedPct(e.cents, total),
      cumulativeCents: running,
      cumulativePct,
      vitalFew,
    });
  }

  const vitalFew = rows.filter((r) => r.vitalFew);
  const vitalFewCents = vitalFew.reduce((s, r) => s + r.cents, 0);
  return {
    rows,
    totalCents: total,
    supplierCount: rows.length,
    vitalFewCount: vitalFew.length,
    vitalFewCents,
    vitalFewPct: total === 0 ? 0 : signedPct(vitalFewCents, total),
  };
}

/**
 * Parse and validate the savings-initiatives CSV. A structural problem throws.
 * A row-level problem (missing field, duplicate id) is recorded as a warning and
 * the row is skipped, so the rest still totals.
 *
 * Expected header: initiative_id,category,baseline_annual,current_annual,target_savings
 */
function parseSavingsCsv(text: string): SavingsResult {
  const rawLines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (rawLines.length === 0) {
    throw new Error("The file is empty.");
  }

  const header = rawLines[0].toLowerCase().replace(/\s+/g, "");
  const expected = "initiative_id,category,baseline_annual,current_annual,target_savings";
  if (header !== expected) {
    throw new Error(`Unexpected header. The first row must be exactly "${expected}".`);
  }

  const rows: Initiative[] = [];
  const warnings: Warning[] = [];
  const seen = new Set<string>();

  for (let i = 1; i < rawLines.length; i++) {
    const rowNumber = i + 1;
    const cells = rawLines[i].split(",").map((cell) => cell.trim());
    if (cells.length !== 5) {
      throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 5.`);
    }
    const [id, category, baselineRaw, currentRaw, targetRaw] = cells;

    let baselineCents: number;
    let currentCents: number;
    let targetCents: number;
    try {
      baselineCents = parseMoneyToCents(baselineRaw);
      currentCents = parseMoneyToCents(currentRaw);
      targetCents = parseMoneyToCents(targetRaw);
    } catch {
      throw new Error(`Row ${rowNumber}: baseline, current, and target must each be a dollar figure of zero or more.`);
    }

    if (id === "") {
      warnings.push({ id: `row ${rowNumber}`, message: `Row ${rowNumber} has no initiative id and was skipped.` });
      continue;
    }
    if (category === "") {
      warnings.push({ id, message: `Initiative ${id} has no category and was skipped.` });
      continue;
    }
    if (seen.has(id)) {
      warnings.push({ id, message: `Initiative ${id} repeats an earlier id and was skipped.` });
      continue;
    }
    seen.add(id);

    const realizedCents = baselineCents - currentCents;
    const attainmentPct = targetCents === 0 ? null : signedPct(realizedCents, targetCents);
    rows.push({
      id,
      category,
      baselineCents,
      currentCents,
      targetCents,
      realizedCents,
      attainmentPct,
      met: realizedCents >= targetCents,
    });
  }

  if (rows.length === 0) {
    throw new Error("No usable savings initiatives were found after validation.");
  }

  const totalTargetCents = rows.reduce((s, r) => s + r.targetCents, 0);
  const totalRealizedCents = rows.reduce((s, r) => s + r.realizedCents, 0);
  return {
    rows,
    warnings,
    totalTargetCents,
    totalRealizedCents,
    overallAttainmentPct: totalTargetCents === 0 ? null : signedPct(totalRealizedCents, totalTargetCents),
  };
}
