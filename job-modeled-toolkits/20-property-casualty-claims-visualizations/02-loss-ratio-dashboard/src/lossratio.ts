/*
 * Pure loss-ratio logic.
 *
 * No DOM access and no I/O. Every function takes inputs and returns values, so
 * the test harness can import this file directly and assert on the numbers.
 *
 * The input is the clean-claims.csv the Claims Aging and Status Funnel writes.
 * This file keeps each claim's latest valuation, groups by line of business and
 * accident year, sums the incurred losses (paid plus case reserve), takes the
 * earned premium once per line and year, and divides incurred by premium to get
 * the loss ratio per cell, per line, per year, and overall. All money is held in
 * integer cents so totals stay exact. The full rules are in spec.md.
 */

interface ClaimRow {
  claimId: string;
  line: string;
  accidentPeriod: string;
  isLatest: boolean;
  incurredCents: number;
  premiumCents: number;
}

interface Cell {
  incurredCents: number;
  premiumCents: number;
  ratio: number; // incurred / premium, e.g. 0.68
}

interface LossRatioGrid {
  lines: string[]; // sorted lines of business present
  periods: string[]; // sorted accident years present
  cells: Map<string, Cell>; // key "line|period", only where a claim exists
  lineTotals: Map<string, Cell>; // per line across all years
  periodTotals: Map<string, Cell>; // per year across all lines
  overall: Cell;
}

const CLEAN_HEADER =
  "claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,incurred,earned_premium,is_latest,age_days,age_bucket,days_to_close";

/** Format a cent amount as a fixed two-decimal string, e.g. 1700000 -> "17000.00". */
function centsToFixed(cents: number): string {
  const dollars = Math.floor(cents / 100);
  const rem = cents % 100;
  return `${dollars}.${String(rem).padStart(2, "0")}`;
}

/** Parse a money string with up to two decimals into exact cents. */
function parseMoneyToCents(raw: string, rowNumber: number, field: string): number {
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
function parseCleanCsv(text: string): ClaimRow[] {
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

  const premiumByGroup = new Map<string, number>();
  const rows: ClaimRow[] = [];

  for (let i = 1; i < lines.length; i++) {
    const rowNumber = i + 1;
    const cells = lines[i].split(",").map((cell) => cell.trim());

    if (cells.length !== 16) {
      throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 16.`);
    }

    const claimId = cells[0];
    const line = cells[1];
    const accidentPeriod = cells[2];
    const incurredRaw = cells[10];
    const premiumRaw = cells[11];
    const isLatestRaw = cells[12];

    if (claimId.length === 0) {
      throw new Error(`Row ${rowNumber}: claim_id is blank.`);
    }
    if (accidentPeriod.length === 0) {
      throw new Error(`Row ${rowNumber}: accident_period is blank.`);
    }
    if (isLatestRaw !== "Y" && isLatestRaw !== "N") {
      throw new Error(`Row ${rowNumber}: is_latest "${isLatestRaw}" must be Y or N.`);
    }

    const incurredCents = parseMoneyToCents(incurredRaw, rowNumber, "incurred");
    const premiumCents = parseMoneyToCents(premiumRaw, rowNumber, "earned_premium");
    if (premiumCents <= 0) {
      throw new Error(`Row ${rowNumber}: earned_premium "${premiumRaw}" must be greater than zero.`);
    }

    const groupKey = `${line}|${accidentPeriod}`;
    const priorPremium = premiumByGroup.get(groupKey);
    if (priorPremium !== undefined && priorPremium !== premiumCents) {
      throw new Error(`Row ${rowNumber}: earned_premium for ${line} ${accidentPeriod} disagrees with an earlier row.`);
    }
    premiumByGroup.set(groupKey, premiumCents);

    rows.push({ claimId, line, accidentPeriod, isLatest: isLatestRaw === "Y", incurredCents, premiumCents });
  }

  if (rows.length === 0) {
    throw new Error("The file has a header but no data rows.");
  }

  return rows;
}

/** Build a cell from incurred and premium cents. */
function makeCell(incurredCents: number, premiumCents: number): Cell {
  return { incurredCents, premiumCents, ratio: premiumCents === 0 ? 0 : incurredCents / premiumCents };
}

/**
 * Group the latest valuation of each claim by line and accident year, sum the
 * incurred losses, take the earned premium once per line and year, and divide to
 * get the loss ratio for every cell, line, year, and the book overall.
 */
function computeLossRatios(rows: ClaimRow[]): LossRatioGrid {
  const latest = rows.filter((r) => r.isLatest);

  const lineSet = new Set<string>();
  const periodSet = new Set<string>();
  const cellIncurred = new Map<string, number>();
  const cellPremium = new Map<string, number>(); // premium per cell, taken once
  const linePremium = new Map<string, Map<string, number>>(); // line -> period -> premium, to total once per cell

  for (const row of latest) {
    lineSet.add(row.line);
    periodSet.add(row.accidentPeriod);
    const key = `${row.line}|${row.accidentPeriod}`;
    cellIncurred.set(key, (cellIncurred.get(key) || 0) + row.incurredCents);
    cellPremium.set(key, row.premiumCents); // same for every claim in the cell
    if (!linePremium.has(row.line)) {
      linePremium.set(row.line, new Map());
    }
    (linePremium.get(row.line) as Map<string, number>).set(row.accidentPeriod, row.premiumCents);
  }

  const lines = Array.from(lineSet).sort();
  const periods = Array.from(periodSet).sort();

  const cells = new Map<string, Cell>();
  for (const [key, incurred] of cellIncurred) {
    cells.set(key, makeCell(incurred, cellPremium.get(key) as number));
  }

  // Per-line totals: incurred summed across that line's cells, premium summed once per cell.
  const lineTotals = new Map<string, Cell>();
  for (const line of lines) {
    let inc = 0;
    let prem = 0;
    for (const period of periods) {
      const cell = cells.get(`${line}|${period}`);
      if (cell) {
        inc += cell.incurredCents;
        prem += cell.premiumCents;
      }
    }
    lineTotals.set(line, makeCell(inc, prem));
  }

  // Per-period totals: incurred and premium summed across lines for that year.
  const periodTotals = new Map<string, Cell>();
  for (const period of periods) {
    let inc = 0;
    let prem = 0;
    for (const line of lines) {
      const cell = cells.get(`${line}|${period}`);
      if (cell) {
        inc += cell.incurredCents;
        prem += cell.premiumCents;
      }
    }
    periodTotals.set(period, makeCell(inc, prem));
  }

  let grandInc = 0;
  let grandPrem = 0;
  for (const cell of cells.values()) {
    grandInc += cell.incurredCents;
    grandPrem += cell.premiumCents;
  }

  return { lines, periods, cells, lineTotals, periodTotals, overall: makeCell(grandInc, grandPrem) };
}

/** Format a ratio as a percentage with one decimal, e.g. 0.68 -> "68.0%". */
function formatRatio(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`;
}
