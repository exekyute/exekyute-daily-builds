/*
 * Pure service-level metrics logic.
 *
 * No DOM access and no I/O. Each function takes inputs and returns values, so
 * the test harness can import this file and assert on the numbers. All rules
 * are written out in spec.md.
 *
 * The dashboard reads two files: an actuals CSV of what each interval did, and
 * an optional staffing-plan CSV produced by the Staffing Planner tool. When the
 * plan is present, each interval is compared against the agents it was meant to
 * have.
 */

interface ActualRow {
  interval: string;
  callsOffered: number;
  callsAnswered: number;
  answeredWithinThreshold: number;
  totalWaitSeconds: number;
  totalHandleSeconds: number;
  agentsScheduled: number;
}

interface DashboardConfig {
  intervalMinutes: number;
  targetSlPct: number;
}

interface IntervalMetric {
  interval: string;
  offered: number;
  slPct: number; // percent of offered calls answered within the threshold
  abandonPct: number; // percent of offered calls not answered
  asaSeconds: number; // average speed of answer
  ahtSeconds: number; // average handle time
  occupancyPct: number; // share of scheduled agent time spent on calls
  agentsScheduled: number;
  requiredAgents: number | null; // from the plan, when joined
  coverage: number | null; // scheduled minus required
  breach: boolean; // service level below target
}

interface DaySummary {
  intervals: number;
  totalOffered: number;
  overallSlPct: number;
  breachCount: number;
  worstInterval: string;
  worstSlPct: number;
}

/** Round half up to a fixed number of decimal places. */
function roundTo(value: number, decimals: number): number {
  const factor = Math.pow(10, decimals);
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

/**
 * Parse and validate the actuals CSV. Throws an Error with a row-numbered
 * message on the first problem found.
 *
 * Header: interval,calls_offered,calls_answered,answered_within_threshold,total_wait_seconds,total_handle_seconds,agents_scheduled
 */
function parseActualsCsv(text: string): ActualRow[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length === 0) {
    throw new Error("The file is empty.");
  }

  const expectedHeader =
    "interval,calls_offered,calls_answered,answered_within_threshold,total_wait_seconds,total_handle_seconds,agents_scheduled";
  if (lines[0].toLowerCase().replace(/\s+/g, "") !== expectedHeader) {
    throw new Error(`Unexpected header. The first row must be exactly "${expectedHeader}".`);
  }

  const seen = new Set<string>();
  const rows: ActualRow[] = [];

  for (let i = 1; i < lines.length; i++) {
    const rowNumber = i + 1;
    const cells = lines[i].split(",").map((cell) => cell.trim());

    if (cells.length !== 7) {
      throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 7.`);
    }

    const [interval, offeredRaw, answeredRaw, withinRaw, waitRaw, handleRaw, scheduledRaw] = cells;

    if (!/^\d{1,2}:\d{2}$/.test(interval)) {
      throw new Error(`Row ${rowNumber}: interval "${interval}" is not in HH:MM form.`);
    }
    if (seen.has(interval)) {
      throw new Error(`Row ${rowNumber}: interval "${interval}" is a duplicate.`);
    }
    seen.add(interval);

    const callsOffered = wholeNonNegative(offeredRaw, rowNumber, "calls_offered");
    const callsAnswered = wholeNonNegative(answeredRaw, rowNumber, "calls_answered");
    const answeredWithinThreshold = wholeNonNegative(withinRaw, rowNumber, "answered_within_threshold");
    const totalWaitSeconds = numberNonNegative(waitRaw, rowNumber, "total_wait_seconds");
    const totalHandleSeconds = numberNonNegative(handleRaw, rowNumber, "total_handle_seconds");
    const agentsScheduled = wholeNonNegative(scheduledRaw, rowNumber, "agents_scheduled");

    if (callsAnswered > callsOffered) {
      throw new Error(`Row ${rowNumber}: calls_answered (${callsAnswered}) cannot exceed calls_offered (${callsOffered}).`);
    }
    if (answeredWithinThreshold > callsAnswered) {
      throw new Error(
        `Row ${rowNumber}: answered_within_threshold (${answeredWithinThreshold}) cannot exceed calls_answered (${callsAnswered}).`,
      );
    }

    rows.push({
      interval,
      callsOffered,
      callsAnswered,
      answeredWithinThreshold,
      totalWaitSeconds,
      totalHandleSeconds,
      agentsScheduled,
    });
  }

  if (rows.length === 0) {
    throw new Error("The file has a header but no data rows.");
  }

  return rows;
}

function wholeNonNegative(raw: string, rowNumber: number, field: string): number {
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 0) {
    throw new Error(`Row ${rowNumber}: ${field} "${raw}" must be a whole number of zero or more.`);
  }
  return value;
}

function numberNonNegative(raw: string, rowNumber: number, field: string): number {
  const value = Number(raw);
  if (!Number.isFinite(value) || value < 0) {
    throw new Error(`Row ${rowNumber}: ${field} "${raw}" must be a number of zero or more.`);
  }
  return value;
}

/**
 * Parse the staffing-plan CSV the Staffing Planner exports, returning a map from
 * interval to required agents. Only the interval and required_agents columns are
 * used here, so a plan with extra columns still loads.
 */
function parsePlanCsv(text: string): Map<string, number> {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length === 0) {
    throw new Error("The plan file is empty.");
  }

  const header = lines[0].toLowerCase().replace(/\s+/g, "").split(",");
  const intervalIdx = header.indexOf("interval");
  const requiredIdx = header.indexOf("required_agents");
  if (intervalIdx === -1 || requiredIdx === -1) {
    throw new Error('The plan file needs "interval" and "required_agents" columns.');
  }

  const plan = new Map<string, number>();
  for (let i = 1; i < lines.length; i++) {
    const cells = lines[i].split(",").map((cell) => cell.trim());
    const interval = cells[intervalIdx];
    const required = Number(cells[requiredIdx]);
    if (interval && Number.isFinite(required)) {
      plan.set(interval, required);
    }
  }
  return plan;
}

/** Compute the metrics for one interval. */
function computeInterval(row: ActualRow, plan: Map<string, number> | null, config: DashboardConfig): IntervalMetric {
  const intervalSeconds = config.intervalMinutes * 60;
  const requiredAgents = plan && plan.has(row.interval) ? (plan.get(row.interval) as number) : null;
  const coverage = requiredAgents === null ? null : row.agentsScheduled - requiredAgents;

  if (row.callsOffered === 0) {
    return {
      interval: row.interval,
      offered: 0,
      slPct: 100,
      abandonPct: 0,
      asaSeconds: 0,
      ahtSeconds: 0,
      occupancyPct: 0,
      agentsScheduled: row.agentsScheduled,
      requiredAgents,
      coverage,
      breach: false,
    };
  }

  const slPct = roundTo((row.answeredWithinThreshold / row.callsOffered) * 100, 2);
  const abandonPct = roundTo(((row.callsOffered - row.callsAnswered) / row.callsOffered) * 100, 2);
  const asaSeconds = row.callsAnswered === 0 ? 0 : roundTo(row.totalWaitSeconds / row.callsAnswered, 2);
  const ahtSeconds = row.callsAnswered === 0 ? 0 : roundTo(row.totalHandleSeconds / row.callsAnswered, 2);
  const occupancyPct =
    row.agentsScheduled === 0 ? 0 : roundTo((row.totalHandleSeconds / (row.agentsScheduled * intervalSeconds)) * 100, 2);

  return {
    interval: row.interval,
    offered: row.callsOffered,
    slPct,
    abandonPct,
    asaSeconds,
    ahtSeconds,
    occupancyPct,
    agentsScheduled: row.agentsScheduled,
    requiredAgents,
    coverage,
    breach: slPct < config.targetSlPct,
  };
}

/** Compute metrics across all intervals. */
function computeMetrics(rows: ActualRow[], plan: Map<string, number> | null, config: DashboardConfig): IntervalMetric[] {
  return rows.map((row) => computeInterval(row, plan, config));
}

/** Roll the intervals up to a day-level summary. Overall SL is volume-weighted. */
function summarize(metrics: IntervalMetric[], rows: ActualRow[]): DaySummary {
  const totalOffered = rows.reduce((sum, r) => sum + r.callsOffered, 0);
  const totalWithin = rows.reduce((sum, r) => sum + r.answeredWithinThreshold, 0);
  const overallSlPct = totalOffered === 0 ? 100 : roundTo((totalWithin / totalOffered) * 100, 2);

  let worst = metrics[0];
  for (const m of metrics) {
    if (m.offered > 0 && m.slPct < worst.slPct) {
      worst = m;
    }
  }

  return {
    intervals: metrics.length,
    totalOffered,
    overallSlPct,
    breachCount: metrics.filter((m) => m.breach).length,
    worstInterval: worst.interval,
    worstSlPct: worst.slPct,
  };
}
