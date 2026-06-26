/*
 * Pure cash-position logic.
 *
 * No DOM access and no I/O. Every function takes inputs and returns values, so
 * the test harness can import this file directly and assert on the numbers.
 *
 * The job is the daily cash position: for each bank account, take the opening
 * balance, add the day's inflows, subtract the day's outflows, and report the
 * closing position, then consolidate across accounts. All amounts are Canadian
 * dollars and all money is held in integer cents so totals are exact. Every rule
 * is written out in spec.md.
 */

type Direction = "opening" | "in" | "out";

interface Movement {
  date: string; // "YYYY-MM-DD"
  account: string; // account id, e.g. "CAD-OPS"
  direction: Direction;
  amountCents: number; // positive integer cents
  description: string;
}

interface AccountPosition {
  account: string;
  openingCents: number;
  inflowCents: number;
  outflowCents: number;
  closingCents: number;
  overdrawn: boolean; // closing below zero
}

interface PositionSummary {
  asOf: string; // latest movement date seen
  accounts: number;
  openingCents: number;
  inflowCents: number;
  outflowCents: number;
  closingCents: number;
  overdrawnCount: number;
}

/** Format integer cents as a Canadian dollar string, e.g. -1700000 -> "-17000.00". */
function centsToFixed(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const dollars = Math.floor(abs / 100);
  const rest = abs % 100;
  return `${sign}${dollars}.${String(rest).padStart(2, "0")}`;
}

/**
 * Parse a money string into integer cents. Accepts an optional leading minus,
 * whole dollars, and at most two decimal places. Throws on anything else.
 */
function parseMoneyToCents(raw: string, allowNegative: boolean): number {
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

/**
 * Parse and validate the cash-movement CSV. Throws an Error with a clear,
 * row-numbered message on the first problem it finds.
 *
 * Expected header: date,account,direction,amount,description
 */
function parsePositionCsv(text: string): Movement[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length === 0) {
    throw new Error("The file is empty.");
  }

  const header = lines[0].toLowerCase().replace(/\s+/g, "");
  if (header !== "date,account,direction,amount,description") {
    throw new Error('Unexpected header. The first row must be exactly "date,account,direction,amount,description".');
  }

  const seenRows = new Set<string>();
  const rows: Movement[] = [];

  for (let i = 1; i < lines.length; i++) {
    const rowNumber = i + 1; // 1-based, counting the header
    const cells = lines[i].split(",").map((cell) => cell.trim());

    if (cells.length !== 5) {
      throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 5.`);
    }

    const [date, account, directionRaw, amountRaw, description] = cells;

    if (!isValidDate(date)) {
      throw new Error(`Row ${rowNumber}: date "${date}" is not a real date in YYYY-MM-DD form.`);
    }
    if (!/^[A-Za-z0-9-]+$/.test(account)) {
      throw new Error(`Row ${rowNumber}: account "${account}" may use only letters, numbers, and hyphens.`);
    }
    const direction = directionRaw.toLowerCase();
    if (direction !== "opening" && direction !== "in" && direction !== "out") {
      throw new Error(`Row ${rowNumber}: direction "${directionRaw}" must be opening, in, or out.`);
    }

    let amountCents: number;
    try {
      amountCents = parseMoneyToCents(amountRaw, false);
    } catch {
      throw new Error(`Row ${rowNumber}: amount "${amountRaw}" must be a dollar figure of zero or more with at most two decimals.`);
    }

    const fingerprint = `${date}|${account}|${direction}|${amountCents}|${description}`;
    if (seenRows.has(fingerprint)) {
      throw new Error(`Row ${rowNumber} is an exact duplicate of an earlier row.`);
    }
    seenRows.add(fingerprint);

    rows.push({ date, account, direction: direction as Direction, amountCents, description });
  }

  if (rows.length === 0) {
    throw new Error("The file has a header but no data rows.");
  }

  return rows;
}

/**
 * Reduce movements to one position per account. Requires exactly one opening row
 * per account. Accounts are returned sorted by id so output is stable.
 */
function computePositions(movements: Movement[]): AccountPosition[] {
  const order: string[] = [];
  const byAccount = new Map<string, { opening: number | null; in: number; out: number }>();

  for (const m of movements) {
    if (!byAccount.has(m.account)) {
      byAccount.set(m.account, { opening: null, in: 0, out: 0 });
      order.push(m.account);
    }
    const entry = byAccount.get(m.account)!;
    if (m.direction === "opening") {
      if (entry.opening !== null) {
        throw new Error(`Account "${m.account}" has more than one opening balance row.`);
      }
      entry.opening = m.amountCents;
    } else if (m.direction === "in") {
      entry.in += m.amountCents;
    } else {
      entry.out += m.amountCents;
    }
  }

  const positions: AccountPosition[] = [];
  for (const account of order) {
    const entry = byAccount.get(account)!;
    if (entry.opening === null) {
      throw new Error(`Account "${account}" is missing an opening balance row.`);
    }
    const closing = entry.opening + entry.in - entry.out;
    positions.push({
      account,
      openingCents: entry.opening,
      inflowCents: entry.in,
      outflowCents: entry.out,
      closingCents: closing,
      overdrawn: closing < 0,
    });
  }

  positions.sort((a, b) => (a.account < b.account ? -1 : a.account > b.account ? 1 : 0));
  return positions;
}

/** Consolidated totals across every account. */
function summarize(positions: AccountPosition[], movements: Movement[]): PositionSummary {
  const asOf = movements.reduce((latest, m) => (m.date > latest ? m.date : latest), movements[0].date);
  return {
    asOf,
    accounts: positions.length,
    openingCents: positions.reduce((s, p) => s + p.openingCents, 0),
    inflowCents: positions.reduce((s, p) => s + p.inflowCents, 0),
    outflowCents: positions.reduce((s, p) => s + p.outflowCents, 0),
    closingCents: positions.reduce((s, p) => s + p.closingCents, 0),
    overdrawnCount: positions.filter((p) => p.overdrawn).length,
  };
}

/**
 * Render closing balances as the CSV the Liquidity Forecast reads. One row per
 * account, sorted by id, balances in dollars with two decimals. The forecast
 * sums the closing_balance column to set its opening cash.
 */
function toClosingBalancesCsv(positions: AccountPosition[]): string {
  const header = "account,closing_balance";
  const body = positions.map((p) => `${p.account},${centsToFixed(p.closingCents)}`);
  return [header, ...body].join("\n");
}
