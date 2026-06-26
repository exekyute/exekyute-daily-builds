/*
 * Pure claims-aging logic.
 *
 * No DOM access and no I/O. Every function takes inputs and returns values, so
 * the test harness can import this file directly and assert on the numbers.
 *
 * The input is a claims valuation register: one row per claim per valuation point
 * (development month), carrying the cumulative paid, the case reserve, the claim
 * status, and the earned premium for that line and accident year. This file
 * validates the register, rolls each claim up to its latest valuation, buckets
 * the still-open inventory by age since the report date, counts the status mix,
 * and works out the average days to close. It also writes the clean per-row CSV
 * the loss-ratio dashboard and the development triangle read. All money is held
 * in integer cents so totals stay exact. The full rules are in spec.md.
 */

interface RegisterRow {
  claimId: string;
  line: string; // Auto, Property, Liability, or Commercial
  accidentPeriod: string; // accident year, "YYYY"
  reportDate: string; // "YYYY-MM-DD"
  valuationDate: string; // "YYYY-MM-DD", the date this row is valued at
  developmentMonth: number; // months of maturity: 12, 24, 36...
  status: string; // open, pending, or closed
  closeDate: string; // "YYYY-MM-DD" when closed, otherwise blank
  paidCents: number; // cumulative paid to date, in cents, zero or more
  reserveCents: number; // case reserve, in cents, zero or more
  premiumCents: number; // earned premium for the line and accident year, in cents
}

interface CleanRow extends RegisterRow {
  incurredCents: number; // paid + reserve at this valuation
  isLatest: boolean; // true for the claim's most recent valuation row
  ageDays: number; // days from report date to the as-of date (claim level)
  ageBucket: string; // 0-30, 31-60, 61-90, 91-180, or 180+
  daysToClose: number | null; // close date minus report date, or null if open
}

interface AgingSummary {
  asOf: string; // the latest valuation date in the register
  totalClaims: number;
  statusCounts: { open: number; pending: number; closed: number };
  buckets: { label: string; count: number }[]; // still-open inventory by age
  closedCount: number;
  avgDaysToClose: number | null; // mean over closed claims, rounded, null if none
  totalIncurredCents: number; // incurred at the latest valuation, all claims
  totalPaidCents: number; // paid at the latest valuation, all claims
}

const KNOWN_LINES = ["Auto", "Property", "Liability", "Commercial"];
const KNOWN_STATUSES = ["open", "pending", "closed"];
const BUCKET_LABELS = ["0-30", "31-60", "61-90", "91-180", "180+"];
const HEADER =
  "claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,earned_premium";

/** Format a cent amount as a fixed two-decimal string, e.g. 1700000 -> "17000.00". */
function centsToFixed(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const dollars = Math.floor(abs / 100);
  const rem = abs % 100;
  return `${sign}${dollars}.${String(rem).padStart(2, "0")}`;
}

/** Parse a money string with up to two decimals into exact cents. Allows zero unless minPositive. */
function parseMoneyToCents(raw: string, rowNumber: number, field: string, minPositive: boolean): number {
  if (!/^\d+(\.\d{1,2})?$/.test(raw)) {
    throw new Error(`Row ${rowNumber}: ${field} "${raw}" must be an amount with up to two decimals and no minus sign.`);
  }
  const [whole, frac = ""] = raw.split(".");
  const cents = Number(whole) * 100 + Number((frac + "00").slice(0, 2));
  if (minPositive && cents <= 0) {
    throw new Error(`Row ${rowNumber}: ${field} "${raw}" must be greater than zero.`);
  }
  return cents;
}

/** True for a well-formed "YYYY-MM-DD" date that names a real calendar day. */
function isDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  const [y, m, d] = value.split("-").map(Number);
  if (m < 1 || m > 12 || d < 1 || d > 31) {
    return false;
  }
  const probe = new Date(Date.UTC(y, m - 1, d));
  return probe.getUTCFullYear() === y && probe.getUTCMonth() === m - 1 && probe.getUTCDate() === d;
}

/** Whole days from one date to another, e.g. 2024-12-01 to 2024-12-31 is 30. */
function daysBetween(from: string, to: string): number {
  const [fy, fm, fd] = from.split("-").map(Number);
  const [ty, tm, td] = to.split("-").map(Number);
  const a = Date.UTC(fy, fm - 1, fd);
  const b = Date.UTC(ty, tm - 1, td);
  return Math.round((b - a) / 86400000);
}

/** The age bucket a day count falls into. Boundaries land in the lower bucket. */
function bucketFor(ageDays: number): string {
  if (ageDays <= 30) {
    return "0-30";
  }
  if (ageDays <= 60) {
    return "31-60";
  }
  if (ageDays <= 90) {
    return "61-90";
  }
  if (ageDays <= 180) {
    return "91-180";
  }
  return "180+";
}

/**
 * Parse and validate the register CSV. Throws an Error with a clear, row-numbered
 * message on the first problem it finds.
 */
function parseRegisterCsv(text: string): RegisterRow[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length === 0) {
    throw new Error("The file is empty.");
  }

  const header = lines[0].toLowerCase().replace(/\s+/g, "");
  if (header !== HEADER) {
    throw new Error(`Unexpected header. The first row must be exactly "${HEADER}".`);
  }

  const seenValuation = new Set<string>(); // claim_id + valuation_date, to catch duplicates
  const claimMeta = new Map<string, string>(); // claim_id -> "line|accidentPeriod|reportDate"
  const premiumByGroup = new Map<string, number>(); // line|accidentPeriod -> premium cents
  const rows: RegisterRow[] = [];

  for (let i = 1; i < lines.length; i++) {
    const rowNumber = i + 1; // 1-based, counting the header
    const cells = lines[i].split(",").map((cell) => cell.trim());

    if (cells.length !== 11) {
      throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 11.`);
    }

    const [claimId, line, accidentPeriod, reportDate, valuationDate, devRaw, statusRaw, closeDate, paidRaw, reserveRaw, premiumRaw] = cells;
    const status = statusRaw.toLowerCase();

    if (claimId.length === 0) {
      throw new Error(`Row ${rowNumber}: claim_id is blank.`);
    }
    if (!KNOWN_LINES.includes(line)) {
      throw new Error(`Row ${rowNumber}: line_of_business "${line}" must be one of Auto, Property, Liability, or Commercial.`);
    }
    if (!/^\d{4}$/.test(accidentPeriod)) {
      throw new Error(`Row ${rowNumber}: accident_period "${accidentPeriod}" must be a four-digit accident year.`);
    }
    if (!isDate(reportDate)) {
      throw new Error(`Row ${rowNumber}: report_date "${reportDate}" is not a valid YYYY-MM-DD date.`);
    }
    if (!isDate(valuationDate)) {
      throw new Error(`Row ${rowNumber}: valuation_date "${valuationDate}" is not a valid YYYY-MM-DD date.`);
    }
    if (daysBetween(reportDate, valuationDate) < 0) {
      throw new Error(`Row ${rowNumber}: valuation_date "${valuationDate}" is before report_date "${reportDate}".`);
    }
    if (!/^\d+$/.test(devRaw) || Number(devRaw) <= 0) {
      throw new Error(`Row ${rowNumber}: development_month "${devRaw}" must be a whole number of months greater than zero.`);
    }
    if (!KNOWN_STATUSES.includes(status)) {
      throw new Error(`Row ${rowNumber}: status "${statusRaw}" must be one of open, pending, or closed.`);
    }
    if (status === "closed") {
      if (closeDate.length === 0) {
        throw new Error(`Row ${rowNumber}: a closed claim must have a close_date.`);
      }
      if (!isDate(closeDate)) {
        throw new Error(`Row ${rowNumber}: close_date "${closeDate}" is not a valid YYYY-MM-DD date.`);
      }
      if (daysBetween(reportDate, closeDate) < 0) {
        throw new Error(`Row ${rowNumber}: close_date "${closeDate}" is before report_date "${reportDate}".`);
      }
    } else if (closeDate.length !== 0) {
      throw new Error(`Row ${rowNumber}: an ${status} claim must not have a close_date.`);
    }

    const paidCents = parseMoneyToCents(paidRaw, rowNumber, "paid_to_date", false);
    const reserveCents = parseMoneyToCents(reserveRaw, rowNumber, "case_reserve", false);
    const premiumCents = parseMoneyToCents(premiumRaw, rowNumber, "earned_premium", true);

    const key = `${claimId}|${valuationDate}`;
    if (seenValuation.has(key)) {
      throw new Error(`Row ${rowNumber}: claim "${claimId}" already has a valuation dated ${valuationDate}.`);
    }
    seenValuation.add(key);

    const meta = `${line}|${accidentPeriod}|${reportDate}`;
    const priorMeta = claimMeta.get(claimId);
    if (priorMeta && priorMeta !== meta) {
      throw new Error(`Row ${rowNumber}: claim "${claimId}" has different line, accident year, or report date than an earlier row.`);
    }
    claimMeta.set(claimId, meta);

    const groupKey = `${line}|${accidentPeriod}`;
    const priorPremium = premiumByGroup.get(groupKey);
    if (priorPremium !== undefined && priorPremium !== premiumCents) {
      throw new Error(`Row ${rowNumber}: earned_premium for ${line} ${accidentPeriod} disagrees with an earlier row.`);
    }
    premiumByGroup.set(groupKey, premiumCents);

    rows.push({ claimId, line, accidentPeriod, reportDate, valuationDate, developmentMonth: Number(devRaw), status, closeDate, paidCents, reserveCents, premiumCents });
  }

  if (rows.length === 0) {
    throw new Error("The file has a header but no data rows.");
  }

  // Cumulative paid must never fall as a claim matures.
  const byClaim = new Map<string, RegisterRow[]>();
  for (const row of rows) {
    const list = byClaim.get(row.claimId) || [];
    list.push(row);
    byClaim.set(row.claimId, list);
  }
  for (const [claimId, list] of byClaim) {
    list.sort((a, b) => a.developmentMonth - b.developmentMonth);
    for (let j = 1; j < list.length; j++) {
      if (list[j].paidCents < list[j - 1].paidCents) {
        throw new Error(`Claim "${claimId}": paid_to_date falls from development month ${list[j - 1].developmentMonth} to ${list[j].developmentMonth}.`);
      }
    }
  }

  return rows;
}

/** The latest valuation date across the whole register, used as the as-of date. */
function asOfDate(rows: RegisterRow[]): string {
  let latest = rows[0].valuationDate;
  for (const row of rows) {
    if (row.valuationDate > latest) {
      latest = row.valuationDate;
    }
  }
  return latest;
}

/** Enrich every register row with incurred, latest flag, age, and days to close. */
function enrich(rows: RegisterRow[]): CleanRow[] {
  const asOf = asOfDate(rows);

  // Find each claim's latest valuation date.
  const latestByClaim = new Map<string, string>();
  for (const row of rows) {
    const current = latestByClaim.get(row.claimId);
    if (current === undefined || row.valuationDate > current) {
      latestByClaim.set(row.claimId, row.valuationDate);
    }
  }

  return rows.map((row) => {
    const ageDays = daysBetween(row.reportDate, asOf);
    return {
      ...row,
      incurredCents: row.paidCents + row.reserveCents,
      isLatest: latestByClaim.get(row.claimId) === row.valuationDate,
      ageDays,
      ageBucket: bucketFor(ageDays),
      daysToClose: row.status === "closed" ? daysBetween(row.reportDate, row.closeDate) : null,
    };
  });
}

/**
 * Summarize the register: status mix, age buckets for the still-open inventory,
 * average days to close, and the incurred and paid totals at the latest valuation.
 */
function summarize(rows: RegisterRow[]): AgingSummary {
  const clean = enrich(rows);
  const latest = clean.filter((r) => r.isLatest);

  const statusCounts = { open: 0, pending: 0, closed: 0 };
  const bucketCounts = new Map<string, number>(BUCKET_LABELS.map((label) => [label, 0]));
  let totalIncurredCents = 0;
  let totalPaidCents = 0;
  let closeDaysSum = 0;
  let closedCount = 0;

  for (const row of latest) {
    statusCounts[row.status as "open" | "pending" | "closed"] += 1;
    totalIncurredCents += row.incurredCents;
    totalPaidCents += row.paidCents;
    if (row.status === "closed") {
      closedCount += 1;
      closeDaysSum += row.daysToClose as number;
    } else {
      bucketCounts.set(row.ageBucket, (bucketCounts.get(row.ageBucket) as number) + 1);
    }
  }

  return {
    asOf: asOfDate(rows),
    totalClaims: latest.length,
    statusCounts,
    buckets: BUCKET_LABELS.map((label) => ({ label, count: bucketCounts.get(label) as number })),
    closedCount,
    avgDaysToClose: closedCount === 0 ? null : Math.round(closeDaysSum / closedCount),
    totalIncurredCents,
    totalPaidCents,
  };
}

/** Render the enriched rows as the clean-claims CSV the other two tools read. */
function toCleanCsv(rows: RegisterRow[]): string {
  const clean = enrich(rows);
  const header =
    "claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,incurred,earned_premium,is_latest,age_days,age_bucket,days_to_close";
  const body = clean.map((r) =>
    [
      r.claimId,
      r.line,
      r.accidentPeriod,
      r.reportDate,
      r.valuationDate,
      String(r.developmentMonth),
      r.status,
      r.closeDate,
      centsToFixed(r.paidCents),
      centsToFixed(r.reserveCents),
      centsToFixed(r.incurredCents),
      centsToFixed(r.premiumCents),
      r.isLatest ? "Y" : "N",
      String(r.ageDays),
      r.ageBucket,
      r.daysToClose === null ? "" : String(r.daysToClose),
    ].join(","),
  );
  return [header, ...body].join("\n");
}
