/*
 * Pure churn, retention, and renewal logic.
 *
 * No DOM access and no I/O. Every function takes inputs and returns values, so
 * the test harness can import this file directly and assert on the numbers.
 *
 * This tool reads the movement table the MRR Movement Waterfall exports and
 * turns it into the retention metrics an analyst reports: the gross MRR churn
 * rate, gross revenue retention, and net revenue retention, each month. It also
 * reads a renewals file and lists the contracts coming up for renewal. All money
 * is held in integer cents so the totals stay exact. The full rules are in
 * spec.md.
 */

interface MovementRow {
  month: string; // "YYYY-MM"
  openingCents: number;
  newCents: number;
  expansionCents: number;
  contractionCents: number;
  churnedCents: number;
  closingCents: number;
}

interface RetentionRow {
  month: string;
  openingCents: number;
  churnedCents: number;
  contractionCents: number;
  expansionCents: number;
  hasBase: boolean; // false when opening is zero, so the rates are not defined
  churnRatePct: number; // churned over opening
  grrPct: number; // (opening - contraction - churned) over opening
  nrrPct: number; // (opening + expansion - contraction - churned) over opening
}

interface RenewalRow {
  customerId: string;
  mrrCents: number;
  renewalMonth: string; // "YYYY-MM"
  termMonths: number;
}

interface RenewalBucket {
  month: string;
  count: number;
  valueCents: number;
}

/** Parse a money string with up to two decimals into exact cents, zero allowed. */
function parseMoneyToCents(raw: string, rowNumber: number, field: string, allowZero: boolean): number {
  if (!/^\d+(\.\d{1,2})?$/.test(raw)) {
    throw new Error(`Row ${rowNumber}: ${field} "${raw}" must be an amount with up to two decimals.`);
  }
  const [whole, frac = ""] = raw.split(".");
  const cents = Number(whole) * 100 + Number((frac + "00").slice(0, 2));
  if (!allowZero && cents <= 0) {
    throw new Error(`Row ${rowNumber}: ${field} "${raw}" must be greater than zero.`);
  }
  return cents;
}

/** True for a well-formed "YYYY-MM" string with a real month number. */
function isMonth(value: string): boolean {
  if (!/^\d{4}-\d{2}$/.test(value)) {
    return false;
  }
  const month = Number(value.slice(5, 7));
  return month >= 1 && month <= 12;
}

/** Whole months from one "YYYY-MM" to another. */
function monthsBetween(from: string, to: string): number {
  const fy = Number(from.slice(0, 4));
  const fm = Number(from.slice(5, 7));
  const ty = Number(to.slice(0, 4));
  const tm = Number(to.slice(5, 7));
  return (ty - fy) * 12 + (tm - fm);
}

/** Round a ratio to a two-decimal percent, half up. */
function ratioPct(part: number, whole: number): number {
  if (whole === 0) {
    return 0;
  }
  return Math.round((part / whole) * 10000) / 100;
}

/**
 * Parse and validate the movement CSV the waterfall exports. Beyond the field
 * checks, every row must reconcile: opening plus new plus expansion minus
 * contraction minus churn must equal closing. A file that does not reconcile is
 * rejected, so the dashboard never reports retention off a broken table.
 *
 * Expected header: month,opening_mrr,new_mrr,expansion_mrr,contraction_mrr,churned_mrr,closing_mrr
 */
function parseMovementCsv(text: string): MovementRow[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length === 0) {
    throw new Error("The file is empty.");
  }

  const header = lines[0].toLowerCase().replace(/\s+/g, "");
  if (header !== "month,opening_mrr,new_mrr,expansion_mrr,contraction_mrr,churned_mrr,closing_mrr") {
    throw new Error('Unexpected header. The movement file must start with the seven columns the waterfall exports.');
  }

  const rows: MovementRow[] = [];
  const seen = new Set<string>();

  for (let i = 1; i < lines.length; i++) {
    const rowNumber = i + 1;
    const cells = lines[i].split(",").map((cell) => cell.trim());

    if (cells.length !== 7) {
      throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 7.`);
    }

    const [month, openRaw, newRaw, expRaw, contrRaw, churnRaw, closeRaw] = cells;
    if (!isMonth(month)) {
      throw new Error(`Row ${rowNumber}: month "${month}" is not a valid YYYY-MM month.`);
    }
    if (seen.has(month)) {
      throw new Error(`Row ${rowNumber}: month "${month}" is a duplicate.`);
    }
    seen.add(month);

    const openingCents = parseMoneyToCents(openRaw, rowNumber, "opening_mrr", true);
    const newCents = parseMoneyToCents(newRaw, rowNumber, "new_mrr", true);
    const expansionCents = parseMoneyToCents(expRaw, rowNumber, "expansion_mrr", true);
    const contractionCents = parseMoneyToCents(contrRaw, rowNumber, "contraction_mrr", true);
    const churnedCents = parseMoneyToCents(churnRaw, rowNumber, "churned_mrr", true);
    const closingCents = parseMoneyToCents(closeRaw, rowNumber, "closing_mrr", true);

    const reconciled = openingCents + newCents + expansionCents - contractionCents - churnedCents;
    if (reconciled !== closingCents) {
      throw new Error(`Row ${rowNumber}: ${month} does not reconcile. Opening plus movement is ${(reconciled / 100).toFixed(2)} but closing is ${(closingCents / 100).toFixed(2)}.`);
    }

    rows.push({ month, openingCents, newCents, expansionCents, contractionCents, churnedCents, closingCents });
  }

  if (rows.length === 0) {
    throw new Error("The file has a header but no data rows.");
  }

  rows.sort((a, b) => (a.month < b.month ? -1 : 1));
  return rows;
}

/**
 * Turn the movement rows into retention metrics. A month that opens at zero has
 * no base to retain against, so its rates are left undefined.
 */
function computeRetention(movement: MovementRow[]): RetentionRow[] {
  return movement.map((m) => {
    const hasBase = m.openingCents > 0;
    const retainedGross = m.openingCents - m.contractionCents - m.churnedCents;
    const retainedNet = m.openingCents + m.expansionCents - m.contractionCents - m.churnedCents;
    return {
      month: m.month,
      openingCents: m.openingCents,
      churnedCents: m.churnedCents,
      contractionCents: m.contractionCents,
      expansionCents: m.expansionCents,
      hasBase,
      churnRatePct: hasBase ? ratioPct(m.churnedCents, m.openingCents) : 0,
      grrPct: hasBase ? ratioPct(retainedGross, m.openingCents) : 0,
      nrrPct: hasBase ? ratioPct(retainedNet, m.openingCents) : 0,
    };
  });
}

/**
 * Parse and validate the renewals CSV.
 *
 * Expected header: customer_id,mrr,renewal_month,term_months
 */
function parseRenewalsCsv(text: string): RenewalRow[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length === 0) {
    throw new Error("The file is empty.");
  }

  const header = lines[0].toLowerCase().replace(/\s+/g, "");
  if (header !== "customer_id,mrr,renewal_month,term_months") {
    throw new Error('Unexpected header. The renewals file must be exactly "customer_id,mrr,renewal_month,term_months".');
  }

  const seen = new Set<string>();
  const rows: RenewalRow[] = [];

  for (let i = 1; i < lines.length; i++) {
    const rowNumber = i + 1;
    const cells = lines[i].split(",").map((cell) => cell.trim());

    if (cells.length !== 4) {
      throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 4.`);
    }

    const [customerId, mrrRaw, renewalMonth, termRaw] = cells;
    if (customerId.length === 0) {
      throw new Error(`Row ${rowNumber}: customer_id is blank.`);
    }
    if (seen.has(customerId)) {
      throw new Error(`Row ${rowNumber}: customer "${customerId}" already has a renewal row.`);
    }
    seen.add(customerId);

    const mrrCents = parseMoneyToCents(mrrRaw, rowNumber, "mrr", false);

    if (!isMonth(renewalMonth)) {
      throw new Error(`Row ${rowNumber}: renewal_month "${renewalMonth}" is not a valid YYYY-MM month.`);
    }
    if (!/^\d+$/.test(termRaw) || Number(termRaw) <= 0) {
      throw new Error(`Row ${rowNumber}: term_months "${termRaw}" must be a whole number of one or more.`);
    }

    rows.push({ customerId, mrrCents, renewalMonth, termMonths: Number(termRaw) });
  }

  if (rows.length === 0) {
    throw new Error("The file has a header but no data rows.");
  }

  return rows;
}

/**
 * Renewals due in the months just after the as-of month, grouped by month. The
 * window runs from the month after as-of through as-of plus the horizon.
 */
function upcomingRenewals(renewals: RenewalRow[], asOfMonth: string, horizonMonths: number): RenewalBucket[] {
  const buckets = new Map<string, RenewalBucket>();
  for (const r of renewals) {
    const gap = monthsBetween(asOfMonth, r.renewalMonth);
    if (gap >= 1 && gap <= horizonMonths) {
      const bucket = buckets.get(r.renewalMonth) || { month: r.renewalMonth, count: 0, valueCents: 0 };
      bucket.count += 1;
      bucket.valueCents += r.mrrCents;
      buckets.set(r.renewalMonth, bucket);
    }
  }
  return Array.from(buckets.values()).sort((a, b) => (a.month < b.month ? -1 : 1));
}
