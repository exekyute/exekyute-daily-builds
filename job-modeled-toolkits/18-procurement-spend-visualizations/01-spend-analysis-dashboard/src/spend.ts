/*
 * Pure spend-analysis logic.
 *
 * No DOM access and no I/O. Every function takes inputs and returns values, so
 * the test harness can load this file directly and assert on the numbers.
 *
 * The job is spend analysis. Take a list of procurement spend lines (one per
 * invoiced purchase-order line), validate and clean them, then total the spend
 * and break it down by category and by supplier. The same clean lines are
 * written out as a normalized CSV that the Supplier Pareto and the PO/Invoice
 * Compliance views read. All amounts are Canadian dollars, net of recoverable
 * taxes, and money is held in integer cents so totals are exact. Every rule is
 * written out in spec.md.
 */

// Categories the procurement taxonomy recognizes. A line whose category is not
// on this list is kept but flagged so it can be reviewed and recoded.
const KNOWN_CATEGORIES = [
  "IT Hardware",
  "Office Supplies",
  "Logistics",
  "Professional Services",
  "Facilities",
];

interface SpendLine {
  lineId: string;
  supplier: string;
  category: string;
  categoryKnown: boolean;
  contractId: string; // "" when the line carries no contract
  onContract: boolean; // a recognized contract id is present
  poCents: number;
  receivedCents: number;
  invoiceCents: number;
  invoiceDate: string; // "YYYY-MM-DD"
}

interface Warning {
  lineId: string; // the line id, or "row N" when the id itself is missing
  kind: "skipped" | "flagged";
  message: string;
}

interface ParseResult {
  lines: SpendLine[];
  warnings: Warning[];
}

interface CategoryTotal {
  category: string;
  cents: number;
  pct: number; // share of total spend, 0 to 100, rounded to two decimals
  known: boolean;
}

interface SupplierTotal {
  supplier: string;
  cents: number;
  pct: number;
}

interface SpendSummary {
  lineCount: number;
  supplierCount: number;
  categoryCount: number;
  totalCents: number;
  onContractCents: number;
  offContractCents: number;
  flaggedCount: number; // lines kept but flagged (unknown category)
}

/** Format integer cents as a plain dollar string, e.g. 135955_00 -> "135955.00". */
function centsToFixed(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const dollars = Math.floor(abs / 100);
  const rest = abs % 100;
  return `${sign}${dollars}.${String(rest).padStart(2, "0")}`;
}

/**
 * Parse a money string into integer cents. Accepts whole dollars and at most two
 * decimal places, zero or more. Throws on anything else.
 */
function parseMoneyToCents(raw: string): number {
  const text = raw.trim();
  if (!/^\d+(\.\d{1,2})?$/.test(text)) {
    throw new Error(`"${raw}" is not a valid dollar amount of zero or more.`);
  }
  const [whole, frac = ""] = text.split(".");
  return Number(whole) * 100 + Number(frac.padEnd(2, "0"));
}

/** True for a real calendar date in strict YYYY-MM-DD form. */
function isValidDate(text: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    return false;
  }
  const [y, m, d] = text.split("-").map(Number);
  if (m < 1 || m > 12 || d < 1 || d > 31) {
    return false;
  }
  const date = new Date(Date.UTC(y, m - 1, d));
  return date.getUTCFullYear() === y && date.getUTCMonth() === m - 1 && date.getUTCDate() === d;
}

/** A contract id the taxonomy recognizes: the letter C, a hyphen, then digits. */
function isContractId(text: string): boolean {
  return /^C-\d+$/.test(text);
}

/**
 * Round a half-up percentage to two decimals. Done on the integer cents so the
 * shares are stable and reproduce the hand-checked figures in spec.md.
 */
function pctOf(part: number, whole: number): number {
  if (whole === 0) {
    return 0;
  }
  return Math.round((part / whole) * 10000) / 100;
}

/**
 * Parse and validate the spend-lines CSV.
 *
 * Two classes of problem are handled differently. A structural problem (wrong
 * header, wrong field count, an amount or date that is not even the right shape)
 * throws, because the file cannot be trusted. A row-level data problem is
 * collected as a warning: a row missing a required business field or repeating
 * an earlier line id is skipped, and a row with an unrecognized category is kept
 * but flagged. The file still processes so the clean rows can be analyzed.
 *
 * Expected header:
 * line_id,supplier,category,contract_id,po_amount,received_amount,invoice_amount,invoice_date
 */
function parseSpendCsv(text: string): ParseResult {
  const rawLines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (rawLines.length === 0) {
    throw new Error("The file is empty.");
  }

  const header = rawLines[0].toLowerCase().replace(/\s+/g, "");
  const expected = "line_id,supplier,category,contract_id,po_amount,received_amount,invoice_amount,invoice_date";
  if (header !== expected) {
    throw new Error(`Unexpected header. The first row must be exactly "${expected}".`);
  }

  const lines: SpendLine[] = [];
  const warnings: Warning[] = [];
  const seenIds = new Set<string>();

  for (let i = 1; i < rawLines.length; i++) {
    const rowNumber = i + 1; // 1-based, counting the header
    const cells = rawLines[i].split(",").map((cell) => cell.trim());

    if (cells.length !== 8) {
      throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 8.`);
    }

    const [lineId, supplier, category, contractId, poRaw, receivedRaw, invoiceRaw, invoiceDate] = cells;

    // Amounts and dates must be the right shape; a malformed value throws.
    let poCents: number;
    let receivedCents: number;
    let invoiceCents: number;
    try {
      poCents = parseMoneyToCents(poRaw);
      receivedCents = parseMoneyToCents(receivedRaw);
      invoiceCents = parseMoneyToCents(invoiceRaw);
    } catch {
      throw new Error(`Row ${rowNumber}: po, received, and invoice amounts must each be a dollar figure of zero or more with at most two decimals.`);
    }
    if (!isValidDate(invoiceDate)) {
      throw new Error(`Row ${rowNumber}: invoice_date "${invoiceDate}" is not a real date in YYYY-MM-DD form.`);
    }

    // Required business fields. A blank one means the row cannot be analyzed.
    if (lineId === "") {
      warnings.push({ lineId: `row ${rowNumber}`, kind: "skipped", message: `Row ${rowNumber} has no line id and was skipped.` });
      continue;
    }
    if (supplier === "") {
      warnings.push({ lineId, kind: "skipped", message: `Line ${lineId} has no supplier and was skipped.` });
      continue;
    }
    if (category === "") {
      warnings.push({ lineId, kind: "skipped", message: `Line ${lineId} has no category and was skipped.` });
      continue;
    }
    if (seenIds.has(lineId)) {
      warnings.push({ lineId, kind: "skipped", message: `Line ${lineId} repeats an earlier line id and was skipped.` });
      continue;
    }
    seenIds.add(lineId);

    const categoryKnown = KNOWN_CATEGORIES.indexOf(category) !== -1;
    if (!categoryKnown) {
      warnings.push({ lineId, kind: "flagged", message: `Line ${lineId} uses category "${category}", which is not in the taxonomy.` });
    }

    const onContract = isContractId(contractId);

    lines.push({
      lineId,
      supplier,
      category,
      categoryKnown,
      contractId: onContract ? contractId : "",
      onContract,
      poCents,
      receivedCents,
      invoiceCents,
      invoiceDate,
    });
  }

  if (lines.length === 0) {
    throw new Error("No usable spend lines were found after validation.");
  }

  return { lines, warnings };
}

/** Total spend by category, sorted by spend descending then by name. */
function totalsByCategory(lines: SpendLine[]): CategoryTotal[] {
  const total = lines.reduce((s, l) => s + l.invoiceCents, 0);
  const byCategory = new Map<string, { cents: number; known: boolean }>();
  for (const l of lines) {
    const entry = byCategory.get(l.category) || { cents: 0, known: l.categoryKnown };
    entry.cents += l.invoiceCents;
    byCategory.set(l.category, entry);
  }
  const rows: CategoryTotal[] = [];
  byCategory.forEach((v, category) => {
    rows.push({ category, cents: v.cents, pct: pctOf(v.cents, total), known: v.known });
  });
  rows.sort((a, b) => (b.cents - a.cents) || (a.category < b.category ? -1 : 1));
  return rows;
}

/** Total spend by supplier, sorted by spend descending then by name. */
function totalsBySupplier(lines: SpendLine[]): SupplierTotal[] {
  const total = lines.reduce((s, l) => s + l.invoiceCents, 0);
  const bySupplier = new Map<string, number>();
  for (const l of lines) {
    bySupplier.set(l.supplier, (bySupplier.get(l.supplier) || 0) + l.invoiceCents);
  }
  const rows: SupplierTotal[] = [];
  bySupplier.forEach((cents, supplier) => {
    rows.push({ supplier, cents, pct: pctOf(cents, total) });
  });
  rows.sort((a, b) => (b.cents - a.cents) || (a.supplier < b.supplier ? -1 : 1));
  return rows;
}

/** Headline totals across every clean line. */
function summarize(lines: SpendLine[], warnings: Warning[]): SpendSummary {
  const suppliers = new Set(lines.map((l) => l.supplier));
  const categories = new Set(lines.map((l) => l.category));
  const onContractCents = lines.filter((l) => l.onContract).reduce((s, l) => s + l.invoiceCents, 0);
  const totalCents = lines.reduce((s, l) => s + l.invoiceCents, 0);
  return {
    lineCount: lines.length,
    supplierCount: suppliers.size,
    categoryCount: categories.size,
    totalCents,
    onContractCents,
    offContractCents: totalCents - onContractCents,
    flaggedCount: warnings.filter((w) => w.kind === "flagged").length,
  };
}

/**
 * Render the clean lines as the normalized CSV the other two views read. One row
 * per clean line, in input order, amounts in dollars with two decimals. The
 * on_contract column is Y or N so the consumer tools do not have to re-derive it.
 */
function toNormalizedCsv(lines: SpendLine[]): string {
  const header = "line_id,supplier,category,contract_id,on_contract,po_amount,received_amount,invoice_amount,invoice_date";
  const body = lines.map((l) =>
    [
      l.lineId,
      l.supplier,
      l.category,
      l.contractId,
      l.onContract ? "Y" : "N",
      centsToFixed(l.poCents),
      centsToFixed(l.receivedCents),
      centsToFixed(l.invoiceCents),
      l.invoiceDate,
    ].join(","),
  );
  return [header, ...body].join("\n");
}
