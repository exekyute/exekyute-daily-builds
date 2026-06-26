/*
 * DOM wiring and chart drawing for the Churn and Renewal Dashboard.
 *
 * This file is the only part that touches the page. It reads the movement file
 * the waterfall exports and a renewals file, calls the pure functions in
 * retention.ts, draws the retention chart and the upcoming-renewals chart, and
 * fills the tables. No retention math lives here.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

let movement: MovementRow[] = [];
let retention: RetentionRow[] = [];
let renewals: RenewalRow[] = [];

const money = new Intl.NumberFormat("en-CA", {
  style: "currency",
  currency: "CAD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) {
    throw new Error(`Missing element #${id}`);
  }
  return node as T;
}

function setMessage(id: string, text: string, kind: "info" | "error"): void {
  const box = el<HTMLDivElement>(id);
  box.textContent = text;
  box.className = `message ${kind}`;
}

function svgEl(name: string, attrs: Record<string, string | number>): SVGElement {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) {
    node.setAttribute(key, String(value));
  }
  return node;
}

function pct(value: number): string {
  return `${value.toFixed(2)}%`;
}

/** Retention chart: NRR and GRR lines per month, with churn rate as faint bars. */
function drawRetentionChart(): void {
  const svg = el<HTMLElement>("retentionChart") as unknown as SVGSVGElement;
  while (svg.firstChild) {
    svg.removeChild(svg.firstChild);
  }
  const points = retention.filter((r) => r.hasBase);
  if (points.length === 0) {
    return;
  }

  const width = 880;
  const height = 340;
  const margin = { top: 24, right: 24, bottom: 48, left: 56 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const maxPct = Math.max(120, ...points.map((r) => Math.max(r.nrrPct, r.grrPct)));
  const yOf = (v: number): number => plotH - (v / maxPct) * plotH;

  const group = svgEl("g", { transform: `translate(${margin.left},${margin.top})` });
  svg.appendChild(group);

  const ticks = 4;
  for (let t = 0; t <= ticks; t++) {
    const value = (maxPct / ticks) * t;
    const y = yOf(value);
    group.appendChild(svgEl("line", { x1: 0, y1: y, x2: plotW, y2: y, class: "grid" }));
    const label = svgEl("text", { x: -10, y: y + 4, class: "axis-label", "text-anchor": "end" });
    label.textContent = `${Math.round(value)}%`;
    group.appendChild(label);
  }

  // The 100% reference line, where revenue is held exactly flat.
  const hundred = yOf(100);
  group.appendChild(svgEl("line", { x1: 0, y1: hundred, x2: plotW, y2: hundred, class: "ref-line" }));

  const slotW = plotW / points.length;
  const barW = Math.min(40, slotW * 0.4);

  // Churn rate bars sit behind the lines, scaled against the same axis.
  points.forEach((r, i) => {
    const cx = i * slotW + slotW / 2;
    const y = yOf(r.churnRatePct);
    group.appendChild(svgEl("rect", { x: cx - barW / 2, y, width: barW, height: plotH - y, class: "churn-bar" }));
    const xLabel = svgEl("text", { x: cx, y: plotH + 20, class: "axis-label", "text-anchor": "middle" });
    xLabel.textContent = r.month;
    group.appendChild(xLabel);
  });

  const lineFor = (key: "nrrPct" | "grrPct", cls: string): void => {
    const poly = points.map((r, i) => `${i * slotW + slotW / 2},${yOf(r[key])}`).join(" ");
    group.appendChild(svgEl("polyline", { points: poly, class: cls }));
    points.forEach((r, i) => {
      group.appendChild(svgEl("circle", { cx: i * slotW + slotW / 2, cy: yOf(r[key]), r: 3.5, class: `${cls}-dot` }));
    });
  };
  lineFor("grrPct", "grr-line");
  lineFor("nrrPct", "nrr-line");
}

function drawRetentionTable(): void {
  const tbody = el<HTMLTableSectionElement>("retentionBody");
  tbody.innerHTML = "";
  for (const r of retention) {
    const tr = document.createElement("tr");
    const cells = [
      r.month,
      money.format(r.openingCents / 100),
      r.hasBase ? pct(r.churnRatePct) : "n/a",
      r.hasBase ? pct(r.grrPct) : "n/a",
      r.hasBase ? pct(r.nrrPct) : "n/a",
    ];
    cells.forEach((value, idx) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (idx > 0) {
        td.className = "num";
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }
}

function drawRenewalsChart(buckets: RenewalBucket[]): void {
  const svg = el<HTMLElement>("renewalChart") as unknown as SVGSVGElement;
  while (svg.firstChild) {
    svg.removeChild(svg.firstChild);
  }
  if (buckets.length === 0) {
    return;
  }

  const width = 880;
  const height = 260;
  const margin = { top: 24, right: 24, bottom: 48, left: 64 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const maxVal = Math.max(1, ...buckets.map((b) => b.valueCents));
  const yOf = (v: number): number => plotH - (v / maxVal) * plotH;

  const group = svgEl("g", { transform: `translate(${margin.left},${margin.top})` });
  svg.appendChild(group);

  const ticks = 4;
  for (let t = 0; t <= ticks; t++) {
    const value = (maxVal / ticks) * t;
    const y = yOf(value);
    group.appendChild(svgEl("line", { x1: 0, y1: y, x2: plotW, y2: y, class: "grid" }));
    const label = svgEl("text", { x: -10, y: y + 4, class: "axis-label", "text-anchor": "end" });
    label.textContent = money.format(value / 100).replace(/\.00$/, "");
    group.appendChild(label);
  }

  const slotW = plotW / buckets.length;
  const barW = Math.min(80, slotW * 0.5);
  buckets.forEach((b, i) => {
    const cx = i * slotW + slotW / 2;
    const y = yOf(b.valueCents);
    group.appendChild(svgEl("rect", { x: cx - barW / 2, y, width: barW, height: plotH - y, class: "renewal-bar" }));
    const valLabel = svgEl("text", { x: cx, y: y - 6, class: "bar-value", "text-anchor": "middle" });
    valLabel.textContent = money.format(b.valueCents / 100).replace(/\.00$/, "");
    group.appendChild(valLabel);
    const xLabel = svgEl("text", { x: cx, y: plotH + 20, class: "axis-label", "text-anchor": "middle" });
    xLabel.textContent = `${b.month} (${b.count})`;
    group.appendChild(xLabel);
  });
}

function drawRenewalsTable(buckets: RenewalBucket[]): void {
  const tbody = el<HTMLTableSectionElement>("renewalBody");
  tbody.innerHTML = "";
  for (const b of buckets) {
    const tr = document.createElement("tr");
    const cells = [b.month, String(b.count), money.format(b.valueCents / 100)];
    cells.forEach((value, idx) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (idx > 0) {
        td.className = "num";
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }
}

function latestWithBase(): RetentionRow | null {
  for (let i = retention.length - 1; i >= 0; i--) {
    if (retention[i].hasBase) {
      return retention[i];
    }
  }
  return null;
}

function drawSummary(buckets: RenewalBucket[]): void {
  const latest = latestWithBase();
  const upcomingValue = buckets.reduce((sum, b) => sum + b.valueCents, 0);
  const upcomingCount = buckets.reduce((sum, b) => sum + b.count, 0);
  const parts: string[] = [];
  if (latest) {
    parts.push(`<div class="stat"><span class="stat-value">${pct(latest.nrrPct)}</span><span class="stat-label">net revenue retention (${latest.month})</span></div>`);
    parts.push(`<div class="stat"><span class="stat-value">${pct(latest.grrPct)}</span><span class="stat-label">gross revenue retention (${latest.month})</span></div>`);
    parts.push(`<div class="stat"><span class="stat-value">${pct(latest.churnRatePct)}</span><span class="stat-label">MRR churn rate (${latest.month})</span></div>`);
  }
  if (renewals.length > 0) {
    parts.push(`<div class="stat"><span class="stat-value">${money.format(upcomingValue / 100)}</span><span class="stat-label">${upcomingCount} renewals in the window</span></div>`);
  }
  el<HTMLDivElement>("summary").innerHTML = parts.length > 0 ? parts.join("") : `<div class="stat"><span class="stat-value">--</span><span class="stat-label">load the movement file to begin</span></div>`;
}

function fillAsOf(): void {
  const select = el<HTMLSelectElement>("asOf");
  select.innerHTML = "";
  for (const r of movement) {
    const opt = document.createElement("option");
    opt.value = r.month;
    opt.textContent = r.month;
    select.appendChild(opt);
  }
  if (movement.length > 0) {
    select.value = movement[movement.length - 1].month;
  }
}

function renderRenewals(): void {
  if (renewals.length === 0) {
    return;
  }
  const asOf = el<HTMLSelectElement>("asOf").value || (movement.length > 0 ? movement[movement.length - 1].month : "2025-05");
  const horizon = Math.max(1, Number(el<HTMLInputElement>("horizon").value) || 3);
  const buckets = upcomingRenewals(renewals, asOf, horizon);
  drawRenewalsChart(buckets);
  drawRenewalsTable(buckets);
  drawSummary(buckets);
}

function renderRetention(): void {
  if (movement.length === 0) {
    return;
  }
  retention = computeRetention(movement);
  drawRetentionChart();
  drawRetentionTable();
  drawSummary([]);
  renderRenewals();
}

function handleMovementFile(file: File): void {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      movement = parseMovementCsv(String(reader.result));
      fillAsOf();
      renderRetention();
      setMessage("movementMessage", `Loaded ${movement.length} months of movement. The chart shows net and gross revenue retention with churn behind it.`, "info");
    } catch (err) {
      movement = [];
      retention = [];
      setMessage("movementMessage", err instanceof Error ? err.message : "Could not read the file.", "error");
    }
  };
  reader.onerror = () => setMessage("movementMessage", "Could not read the file.", "error");
  reader.readAsText(file);
}

function handleRenewalsFile(file: File): void {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      renewals = parseRenewalsCsv(String(reader.result));
      renderRenewals();
      setMessage("renewalMessage", `Loaded ${renewals.length} renewal records. Adjust the as-of month and horizon to change the window.`, "info");
    } catch (err) {
      renewals = [];
      setMessage("renewalMessage", err instanceof Error ? err.message : "Could not read the file.", "error");
    }
  };
  reader.onerror = () => setMessage("renewalMessage", "Could not read the file.", "error");
  reader.readAsText(file);
}

function init(): void {
  el<HTMLInputElement>("movementInput").addEventListener("change", (event) => {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      handleMovementFile(input.files[0]);
    }
  });
  el<HTMLInputElement>("renewalInput").addEventListener("change", (event) => {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      handleRenewalsFile(input.files[0]);
    }
  });
  el<HTMLSelectElement>("asOf").addEventListener("change", renderRenewals);
  el<HTMLInputElement>("horizon").addEventListener("change", renderRenewals);
}

document.addEventListener("DOMContentLoaded", init);
