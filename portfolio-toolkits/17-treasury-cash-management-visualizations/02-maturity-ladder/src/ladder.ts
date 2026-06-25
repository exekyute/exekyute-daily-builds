/*
 * Pure maturity-ladder logic.
 *
 * No DOM access and no I/O. Every function takes inputs and returns values, so
 * the test harness can import this file directly and assert on the numbers.
 *
 * The job is a debt and obligation maturity ladder: take a list of dated
 * obligations, measure each one's distance from an as-of date, and bucket the
 * amounts into weekly rungs so the analyst can see when cash has to go out. All
 * amounts are Canadian dollars held in integer cents. Every rule is in spec.md.
 */

const WEEKS = 13;
const MS_PER_DAY = 86400000;

interface Obligation {
  id: string;
  counterparty: string;
  type: string;
  dueDate: string; // "YYYY-MM-DD"
  amountCents: number; // positive integer cents
}

type BucketKind = "overdue" | "week" | "beyond";

interface Bucket {
  kind: BucketKind;
  week: number; // 1..13 for week buckets, 0 otherwise
  label: string; // "Overdue", "W1" .. "W13", "Beyond"
  startDate: string; // start date of a week bucket, "" otherwise
  totalCents: number;
  count: number;
  heavy: boolean; // total at or above the concentration threshold
}

interface LadderSummary {
  obligations: number;
  totalCents: number;
  overdueCents: number;
  overdueCount: number;
  beyondCents: number;
  within13Cents: number; // overdue folded in plus weeks 1..13
  peakLabel: string;
  peakCents: number;
}

/** Format integer cents as a fixed dollar string, e.g. 7675000 -> "76750.00". */
function centsToFixed(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

/** Parse a positive money string into integer cents, at most two decimals. */
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

/** UTC midnight milliseconds for a YYYY-MM-DD string. */
function dateToMs(text: string): number {
  const [y, m, d] = text.split("-").map(Number);
  return Date.UTC(y, m - 1, d);
}

/** A YYYY-MM-DD string a given number of days after another date. */
function addDays(text: string, days: number): string {
  const date = new Date(dateToMs(text) + days * MS_PER_DAY);
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, "0");
  const d = String(date.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/**
 * Place a due date relative to the as-of date. A date before the as-of date is
 * overdue. Otherwise the week is `floor(days / 7) + 1`; anything past week 13 is
 * beyond. The as-of date itself lands in week 1.
 */
function classify(asOf: string, dueDate: string): { kind: BucketKind; week: number } {
  const diffDays = Math.floor((dateToMs(dueDate) - dateToMs(asOf)) / MS_PER_DAY);
  if (diffDays < 0) {
    return { kind: "overdue", week: 0 };
  }
  const week = Math.floor(diffDays / 7) + 1;
  if (week > WEEKS) {
    return { kind: "beyond", week: 0 };
  }
  return { kind: "week", week };
}

/**
 * Parse and validate the obligations CSV. Throws an Error with a clear,
 * row-numbered message on the first problem it finds.
 *
 * Expected header: obligation_id,counterparty,type,due_date,amount
 */
function parseObligationCsv(text: string): Obligation[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length === 0) {
    throw new Error("The file is empty.");
  }

  const header = lines[0].toLowerCase().replace(/\s+/g, "");
  if (header !== "obligation_id,counterparty,type,due_date,amount") {
    throw new Error('Unexpected header. The first row must be exactly "obligation_id,counterparty,type,due_date,amount".');
  }

  const seenIds = new Set<string>();
  const rows: Obligation[] = [];

  for (let i = 1; i < lines.length; i++) {
    const rowNumber = i + 1;
    const cells = lines[i].split(",").map((cell) => cell.trim());

    if (cells.length !== 5) {
      throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 5.`);
    }

    const [id, counterparty, type, dueDate, amountRaw] = cells;

    if (id.length === 0) {
      throw new Error(`Row ${rowNumber}: obligation_id is blank.`);
    }
    if (seenIds.has(id)) {
      throw new Error(`Row ${rowNumber}: obligation_id "${id}" is a duplicate.`);
    }
    seenIds.add(id);

    if (counterparty.length === 0) {
      throw new Error(`Row ${rowNumber}: counterparty is blank.`);
    }
    if (type.length === 0) {
      throw new Error(`Row ${rowNumber}: type is blank.`);
    }
    if (!isValidDate(dueDate)) {
      throw new Error(`Row ${rowNumber}: due_date "${dueDate}" is not a real date in YYYY-MM-DD form.`);
    }

    let amountCents: number;
    try {
      amountCents = parseMoneyToCents(amountRaw);
    } catch {
      throw new Error(`Row ${rowNumber}: amount "${amountRaw}" must be a dollar figure of zero or more with at most two decimals.`);
    }

    rows.push({ id, counterparty, type, dueDate, amountCents });
  }

  if (rows.length === 0) {
    throw new Error("The file has a header but no data rows.");
  }

  return rows;
}

/** True when an obligation falls before the as-of date. */
function isOverdue(asOf: string, obligation: Obligation): boolean {
  return classify(asOf, obligation.dueDate).kind === "overdue";
}

/**
 * Bucket the obligations into Overdue, weeks 1..13, and Beyond. A week bucket is
 * marked heavy when its total reaches the concentration threshold.
 */
function buildLadder(obligations: Obligation[], asOf: string, thresholdCents: number): Bucket[] {
  const buckets: Bucket[] = [];
  buckets.push({ kind: "overdue", week: 0, label: "Overdue", startDate: "", totalCents: 0, count: 0, heavy: false });
  for (let w = 1; w <= WEEKS; w++) {
    buckets.push({ kind: "week", week: w, label: `W${w}`, startDate: addDays(asOf, (w - 1) * 7), totalCents: 0, count: 0, heavy: false });
  }
  buckets.push({ kind: "beyond", week: 0, label: "Beyond", startDate: "", totalCents: 0, count: 0, heavy: false });

  const indexOfWeek = (w: number): number => w; // overdue at 0, week w at index w
  for (const ob of obligations) {
    const place = classify(asOf, ob.dueDate);
    let idx: number;
    if (place.kind === "overdue") {
      idx = 0;
    } else if (place.kind === "beyond") {
      idx = buckets.length - 1;
    } else {
      idx = indexOfWeek(place.week);
    }
    buckets[idx].totalCents += ob.amountCents;
    buckets[idx].count += 1;
  }

  for (const b of buckets) {
    if (b.kind === "week" && b.totalCents >= thresholdCents && b.totalCents > 0) {
      b.heavy = true;
    }
  }

  return buckets;
}

/** Roll the buckets up into the headline numbers shown above the chart. */
function summarize(buckets: Bucket[]): LadderSummary {
  const overdue = buckets.find((b) => b.kind === "overdue")!;
  const beyond = buckets.find((b) => b.kind === "beyond")!;
  const weeks = buckets.filter((b) => b.kind === "week");
  const within13 = overdue.totalCents + weeks.reduce((s, b) => s + b.totalCents, 0);

  let peak = buckets[0];
  for (const b of buckets) {
    if (b.totalCents > peak.totalCents) {
      peak = b;
    }
  }

  return {
    obligations: buckets.reduce((s, b) => s + b.count, 0),
    totalCents: buckets.reduce((s, b) => s + b.totalCents, 0),
    overdueCents: overdue.totalCents,
    overdueCount: overdue.count,
    beyondCents: beyond.totalCents,
    within13Cents: within13,
    peakLabel: peak.label,
    peakCents: peak.totalCents,
  };
}

/**
 * Render the weekly maturities as the CSV the Liquidity Forecast reads. One row
 * per week, 1..13. Overdue amounts are folded into week 1 because they still
 * have to be paid right away; obligations beyond 13 weeks are left out. The
 * forecast adds the debt_due column to each week's outflows.
 */
function toMaturitiesByWeekCsv(obligations: Obligation[], asOf: string): string {
  const weekTotals = new Array<number>(WEEKS + 1).fill(0); // 1..13 used
  for (const ob of obligations) {
    const place = classify(asOf, ob.dueDate);
    if (place.kind === "overdue") {
      weekTotals[1] += ob.amountCents;
    } else if (place.kind === "week") {
      weekTotals[place.week] += ob.amountCents;
    }
  }
  const header = "week,debt_due";
  const body: string[] = [];
  for (let w = 1; w <= WEEKS; w++) {
    body.push(`${w},${centsToFixed(weekTotals[w])}`);
  }
  return [header, ...body].join("\n");
}
