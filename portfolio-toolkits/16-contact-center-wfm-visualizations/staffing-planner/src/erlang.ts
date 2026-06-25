/*
 * Pure workforce-management staffing logic.
 *
 * No DOM access and no I/O. Every function takes inputs and returns values, so
 * the test harness can import this file directly and assert on the numbers.
 *
 * The model is Erlang C, the standard queueing formula contact centres use to
 * size staffing for a given call volume and service-level target. All rules are
 * written out in spec.md.
 */

interface IntervalForecast {
  interval: string; // "HH:MM" label for the half-hour (or chosen length) interval
  callsOffered: number; // calls expected to arrive in the interval
  ahtSeconds: number; // average handle time per call, in seconds
}

interface PlannerConfig {
  intervalMinutes: number; // length of each interval, e.g. 30
  targetSlPct: number; // service-level target, e.g. 80 means "80% answered in time"
  targetAnswerSeconds: number; // the "in time" threshold, e.g. 20 seconds
  shrinkagePct: number; // planned unproductive time, e.g. 30 means 30%
}

interface StaffingResult {
  interval: string;
  trafficErlangs: number; // offered load in Erlangs
  requiredAgents: number; // minimum agents on calls to hit the SL target
  projectedSlPct: number; // service level those agents are projected to deliver
  occupancyPct: number; // share of agent time spent on calls at that staffing
  scheduledWithShrinkage: number; // agents to roster once shrinkage is added
}

/** Round half up to a fixed number of decimal places. */
function roundTo(value: number, decimals: number): number {
  const factor = Math.pow(10, decimals);
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

/** Offered load in Erlangs: total talk-seconds divided by interval seconds. */
function trafficIntensity(callsOffered: number, ahtSeconds: number, intervalSeconds: number): number {
  return (callsOffered * ahtSeconds) / intervalSeconds;
}

/**
 * Erlang B blocking probability, built up with the stable iterative recursion.
 * B(0) = 1; B(n) = (A * B(n-1)) / (n + A * B(n-1)).
 */
function erlangB(agents: number, trafficA: number): number {
  let b = 1;
  for (let n = 1; n <= agents; n++) {
    b = (trafficA * b) / (n + trafficA * b);
  }
  return b;
}

/**
 * Erlang C probability that an arriving call has to wait at all.
 * Returns 1 when the centre is unstable (agents at or below the offered load).
 */
function erlangC(agents: number, trafficA: number): number {
  if (agents <= trafficA) {
    return 1;
  }
  const b = erlangB(agents, trafficA);
  const rho = trafficA / agents;
  return b / (1 - rho * (1 - b));
}

/**
 * Projected service level: the fraction of calls answered within the target
 * answer time, given a number of agents. Returns a fraction between 0 and 1.
 */
function serviceLevel(agents: number, trafficA: number, ahtSeconds: number, targetSeconds: number): number {
  if (agents <= trafficA) {
    return 0;
  }
  const c = erlangC(agents, trafficA);
  const sl = 1 - c * Math.exp((-(agents - trafficA) * targetSeconds) / ahtSeconds);
  return sl < 0 ? 0 : sl;
}

/** Smallest agent count whose projected service level meets the target fraction. */
function requiredAgents(trafficA: number, ahtSeconds: number, targetSeconds: number, targetSlFraction: number): number {
  let n = Math.max(1, Math.floor(trafficA) + 1);
  while (serviceLevel(n, trafficA, ahtSeconds, targetSeconds) < targetSlFraction) {
    n += 1;
    if (n > 10000) {
      break; // guard against a target that can never be met
    }
  }
  return n;
}

/** Agents to roster once shrinkage is added: required / (1 - shrinkage), rounded up. */
function scheduledWithShrinkage(required: number, shrinkagePct: number): number {
  const keep = 1 - shrinkagePct / 100;
  return Math.ceil(required / keep);
}

/** Run the full model for one interval. */
function planInterval(forecast: IntervalForecast, config: PlannerConfig): StaffingResult {
  const intervalSeconds = config.intervalMinutes * 60;
  const trafficA = trafficIntensity(forecast.callsOffered, forecast.ahtSeconds, intervalSeconds);
  const targetFraction = config.targetSlPct / 100;

  if (forecast.callsOffered === 0) {
    return {
      interval: forecast.interval,
      trafficErlangs: 0,
      requiredAgents: 0,
      projectedSlPct: 100,
      occupancyPct: 0,
      scheduledWithShrinkage: 0,
    };
  }

  const required = requiredAgents(trafficA, forecast.ahtSeconds, config.targetAnswerSeconds, targetFraction);
  const projectedSl = serviceLevel(required, trafficA, forecast.ahtSeconds, config.targetAnswerSeconds);
  const occupancy = trafficA / required;

  return {
    interval: forecast.interval,
    trafficErlangs: roundTo(trafficA, 2),
    requiredAgents: required,
    projectedSlPct: roundTo(projectedSl * 100, 2),
    occupancyPct: roundTo(occupancy * 100, 2),
    scheduledWithShrinkage: scheduledWithShrinkage(required, config.shrinkagePct),
  };
}

/** Run the model across a full day of intervals. */
function planAll(forecasts: IntervalForecast[], config: PlannerConfig): StaffingResult[] {
  return forecasts.map((fc) => planInterval(fc, config));
}

/**
 * Parse and validate a forecast CSV. Throws an Error with a clear, row-numbered
 * message on the first problem it finds.
 *
 * Expected header: interval,calls_offered,aht_seconds
 */
function parseForecastCsv(text: string): IntervalForecast[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length === 0) {
    throw new Error("The file is empty.");
  }

  const header = lines[0].toLowerCase().replace(/\s+/g, "");
  if (header !== "interval,calls_offered,aht_seconds") {
    throw new Error('Unexpected header. The first row must be exactly "interval,calls_offered,aht_seconds".');
  }

  const seen = new Set<string>();
  const rows: IntervalForecast[] = [];

  for (let i = 1; i < lines.length; i++) {
    const rowNumber = i + 1; // 1-based, counting the header
    const cells = lines[i].split(",").map((cell) => cell.trim());

    if (cells.length !== 3) {
      throw new Error(`Row ${rowNumber} has ${cells.length} fields, expected 3.`);
    }

    const [interval, callsRaw, ahtRaw] = cells;

    if (!/^\d{1,2}:\d{2}$/.test(interval)) {
      throw new Error(`Row ${rowNumber}: interval "${interval}" is not in HH:MM form.`);
    }
    if (seen.has(interval)) {
      throw new Error(`Row ${rowNumber}: interval "${interval}" is a duplicate.`);
    }
    seen.add(interval);

    const callsOffered = Number(callsRaw);
    if (!Number.isInteger(callsOffered) || callsOffered < 0) {
      throw new Error(`Row ${rowNumber}: calls_offered "${callsRaw}" must be a whole number of zero or more.`);
    }

    const ahtSeconds = Number(ahtRaw);
    if (!Number.isFinite(ahtSeconds) || ahtSeconds <= 0) {
      throw new Error(`Row ${rowNumber}: aht_seconds "${ahtRaw}" must be a positive number.`);
    }

    rows.push({ interval, callsOffered, ahtSeconds });
  }

  if (rows.length === 0) {
    throw new Error("The file has a header but no data rows.");
  }

  return rows;
}

/** Render staffing results as the plan CSV the dashboard tool reads. */
function toPlanCsv(results: StaffingResult[]): string {
  const header = "interval,traffic_erlangs,required_agents,projected_sl_pct,occupancy_pct,scheduled_with_shrinkage";
  const body = results.map((r) =>
    [
      r.interval,
      r.trafficErlangs.toFixed(2),
      r.requiredAgents,
      r.projectedSlPct.toFixed(2),
      r.occupancyPct.toFixed(2),
      r.scheduledWithShrinkage,
    ].join(","),
  );
  return [header, ...body].join("\n");
}
