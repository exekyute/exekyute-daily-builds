/*
 * Pure MRR movement logic.
 *
 * No DOM access and no I/O. Every function takes inputs and returns values, so
 * the test harness can import this file directly and assert on the numbers.
 *
 * The model takes a monthly recurring-revenue ledger (one row per customer per
 * month they are active) and rolls each month forward from the one before it,
 * splitting the change into new, expansion, contraction, and churned recurring
 * revenue. Opening plus new plus expansion minus contraction minus churn equals
 * closing, every month. All money is held in integer cents so totals stay exact.
 * The full rules are written out in spec.md.
 */

interface LedgerRow {
  customerId: string;
  plan: string; // Basic, Pro, or Enterprise
  signupMonth: string; // "YYYY-MM"
  month: string; // "YYYY-MM", the month this MRR applies to
  mrrCents: number; // recurring revenue for that month, in cents, greater than zero
}

interface MovementRow {
  month: string; // "YYYY-MM"
  openingCents: number; // total MRR at the end of the prior month
  newCents: number; // MRR from customers active this month but not last
  expansionCents: number; // increase in MRR from customers active both months
  contractionCents: number; // decrease in MRR from customers active both months
  churnedCents: number; // MRR lost from customers active last month but not this
  closingCents: number; // total MRR at the end of this month
}

const KNOWN_PLANS = ["Basic", "Pro", "Enterprise"];

/** Format a cent amount as a fixed two-decimal dollar string, e.g. 250000 -> "2500.00". */
function centsToFixed(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const dollars = Math.floor(abs / 100);
  const rem = abs % 100;
  return `${sign}${dollars}.${String(rem).padStart(2, "0")}`;
}

/** Parse a positive money string with up to two decimals into exact cents. */
function parseMoneyToCents(raw: string, rowNumber: number, field: string): number {
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
function isMonth(value: string): boolean {
  if (!/^\d{4}-\d{2}$/.test(value)) {
    return false;
  }
  const month = Number(value.slice(5, 7));
  return month >= 1 && month <= 12;
}

/** Whole months from one "YYYY-MM" to another, e.g. 2025-01 to 2025-04 is 3. */
function monthsBetween(from: string, to: string): number {
  const fy = Number(from.slice(0, 4));
  const fm = Number(from.slice(5, 7));
  const ty = Number(to.slice(0, 4));
  const tm = Number(to.slice(5, 7));
  return (ty - fy) * 12 + (tm - fm);
}

/**
 * Parse and validate the ledger CSV. Throws an Error with a clear, row-numbered
 * message on the first problem it finds.
 *
 * Expected header: customer_id,plan,signup_month,month,mrr
 */
function parseLedgerCsv(text: string): LedgerRow[] {
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

  const seen = new Set<string>(); // customer_id + month, to catch duplicates
  const rows: LedgerRow[] = [];

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

/** Every distinct month in the ledger, in ascending order. */
function monthsInLedger(rows: LedgerRow[]): string[] {
  const set = new Set<string>();
  for (const row of rows) {
    set.add(row.month);
  }
  return Array.from(set).sort();
}

/** Map of customer id to MRR cents for a single month. */
function mrrByCustomer(rows: LedgerRow[], month: string): Map<string, number> {
  const map = new Map<string, number>();
  for (const row of rows) {
    if (row.month === month) {
      map.set(row.customerId, row.mrrCents);
    }
  }
  return map;
}

/**
 * Roll every month forward from the one before it and split the change into the
 * four movement components. The first month has no prior month, so its whole
 * book counts as new.
 */
function computeMovement(rows: LedgerRow[]): MovementRow[] {
  const months = monthsInLedger(rows);
  const result: MovementRow[] = [];
  let prior = new Map<string, number>();

  for (const month of months) {
    const current = mrrByCustomer(rows, month);

    let opening = 0;
    for (const v of prior.values()) {
      opening += v;
    }
    let closing = 0;
    for (const v of current.values()) {
      closing += v;
    }

    let newCents = 0;
    let expansionCents = 0;
    let contractionCents = 0;
    let churnedCents = 0;

    for (const [id, cur] of current) {
      if (!prior.has(id)) {
        newCents += cur;
      } else {
        const was = prior.get(id) as number;
        if (cur > was) {
          expansionCents += cur - was;
        } else if (cur < was) {
          contractionCents += was - cur;
        }
      }
    }
    for (const [id, was] of prior) {
      if (!current.has(id)) {
        churnedCents += was;
      }
    }

    result.push({
      month,
      openingCents: opening,
      newCents,
      expansionCents,
      contractionCents,
      churnedCents,
      closingCents: closing,
    });

    prior = current;
  }

  return result;
}

/** Render the movement table as the CSV the churn and renewal dashboard reads. */
function toMovementCsv(rows: MovementRow[]): string {
  const header = "month,opening_mrr,new_mrr,expansion_mrr,contraction_mrr,churned_mrr,closing_mrr";
  const body = rows.map((r) =>
    [
      r.month,
      centsToFixed(r.openingCents),
      centsToFixed(r.newCents),
      centsToFixed(r.expansionCents),
      centsToFixed(r.contractionCents),
      centsToFixed(r.churnedCents),
      centsToFixed(r.closingCents),
    ].join(","),
  );
  return [header, ...body].join("\n");
}
