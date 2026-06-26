/*
 * DOM wiring and chart drawing for the Service-Level Dashboard.
 *
 * This file is the only part that touches the page. It reads the actuals file
 * and the optional plan file, calls the pure functions in metrics.js, draws the
 * service-level timeline and the coverage strip, and fills the table. No metric
 * math lives here.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

let actualsRows: ActualRow[] = [];
let planMap: Map<string, number> | null = null;

function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) {
    throw new Error(`Missing element #${id}`);
  }
  return node as T;
}

function readConfig(): DashboardConfig {
  return {
    intervalMinutes: Number(el<HTMLInputElement>("intervalMinutes").value),
    targetSlPct: Number(el<HTMLInputElement>("targetSlPct").value),
  };
}

function showError(message: string): void {
  const box = el<HTMLDivElement>("message");
  box.textContent = message;
  box.className = "message error";
}

function showInfo(message: string): void {
  const box = el<HTMLDivElement>("message");
  box.textContent = message;
  box.className = "message info";
}

function svgEl(name: string, attrs: Record<string, string | number>): SVGElement {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) {
    node.setAttribute(key, String(value));
  }
  return node;
}

function clear(svg: SVGSVGElement): void {
  while (svg.firstChild) {
    svg.removeChild(svg.firstChild);
  }
}

/**
 * Service-level timeline: one bar per interval against a 0 to 100 percent axis,
 * with a dashed line at the target. Bars that miss the target are drawn in the
 * breach colour.
 */
function drawServiceLevel(metrics: IntervalMetric[], targetSlPct: number): void {
  const svg = el<HTMLElement>("slChart") as unknown as SVGSVGElement;
  clear(svg);

  const width = 880;
  const height = 320;
  const margin = { top: 20, right: 20, bottom: 48, left: 44 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const yScale = (pct: number): number => plotH - (pct / 100) * plotH;
  const group = svgEl("g", { transform: `translate(${margin.left},${margin.top})` });
  svg.appendChild(group);

  for (let t = 0; t <= 4; t++) {
    const pct = 25 * t;
    const y = yScale(pct);
    group.appendChild(svgEl("line", { x1: 0, y1: y, x2: plotW, y2: y, class: "grid" }));
    const label = svgEl("text", { x: -10, y: y + 4, class: "axis-label", "text-anchor": "end" });
    label.textContent = `${pct}%`;
    group.appendChild(label);
  }

  const slotW = plotW / metrics.length;
  const barW = Math.min(34, slotW * 0.6);

  metrics.forEach((m, i) => {
    const cx = i * slotW + slotW / 2;
    const y = yScale(m.slPct);
    group.appendChild(
      svgEl("rect", {
        x: cx - barW / 2,
        y,
        width: barW,
        height: plotH - y,
        class: m.breach ? "bar-breach" : "bar-met",
        rx: 2,
      }),
    );
    if (metrics.length <= 16 || i % 2 === 0) {
      const xlabel = svgEl("text", { x: cx, y: plotH + 20, class: "axis-label", "text-anchor": "middle" });
      xlabel.textContent = m.interval;
      group.appendChild(xlabel);
    }
  });

  // Target threshold line, drawn last so it sits on top.
  const targetY = yScale(targetSlPct);
  group.appendChild(svgEl("line", { x1: 0, y1: targetY, x2: plotW, y2: targetY, class: "target-line" }));
  const targetLabel = svgEl("text", { x: plotW - 4, y: targetY - 6, class: "target-label", "text-anchor": "end" });
  targetLabel.textContent = `target ${targetSlPct}%`;
  group.appendChild(targetLabel);
}

/**
 * Coverage strip: scheduled versus required agents per interval. Only drawn when
 * a plan file is loaded. Intervals short of plan are flagged.
 */
function drawCoverage(metrics: IntervalMetric[]): void {
  const section = el<HTMLElement>("coverageSection");
  const hasPlan = metrics.some((m) => m.requiredAgents !== null);
  section.style.display = hasPlan ? "block" : "none";
  if (!hasPlan) {
    return;
  }

  const svg = el<HTMLElement>("coverageChart") as unknown as SVGSVGElement;
  clear(svg);

  const width = 880;
  const height = 260;
  const margin = { top: 20, right: 20, bottom: 48, left: 44 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const maxAgents = Math.max(
    1,
    ...metrics.map((m) => Math.max(m.agentsScheduled, m.requiredAgents ?? 0)),
  );
  const yScale = (v: number): number => plotH - (v / maxAgents) * plotH;
  const group = svgEl("g", { transform: `translate(${margin.left},${margin.top})` });
  svg.appendChild(group);

  for (let t = 0; t <= 4; t++) {
    const value = (maxAgents / 4) * t;
    const y = yScale(value);
    group.appendChild(svgEl("line", { x1: 0, y1: y, x2: plotW, y2: y, class: "grid" }));
    const label = svgEl("text", { x: -10, y: y + 4, class: "axis-label", "text-anchor": "end" });
    label.textContent = String(Math.round(value));
    group.appendChild(label);
  }

  const slotW = plotW / metrics.length;
  const barW = Math.min(28, slotW * 0.36);

  metrics.forEach((m, i) => {
    const cx = i * slotW + slotW / 2;
    const required = m.requiredAgents ?? 0;

    const reqY = yScale(required);
    group.appendChild(
      svgEl("rect", { x: cx - barW, y: reqY, width: barW, height: plotH - reqY, class: "bar-required" }),
    );

    const schedY = yScale(m.agentsScheduled);
    const understaffed = m.coverage !== null && m.coverage < 0;
    group.appendChild(
      svgEl("rect", {
        x: cx,
        y: schedY,
        width: barW,
        height: plotH - schedY,
        class: understaffed ? "bar-short" : "bar-scheduled",
      }),
    );

    if (metrics.length <= 16 || i % 2 === 0) {
      const xlabel = svgEl("text", { x: cx, y: plotH + 20, class: "axis-label", "text-anchor": "middle" });
      xlabel.textContent = m.interval;
      group.appendChild(xlabel);
    }
  });
}

function drawSummary(metrics: IntervalMetric[], rows: ActualRow[]): void {
  const s = summarize(metrics, rows);
  el<HTMLDivElement>("summary").innerHTML = `
    <div class="stat"><span class="stat-value">${s.overallSlPct.toFixed(2)}%</span><span class="stat-label">overall service level</span></div>
    <div class="stat"><span class="stat-value">${s.totalOffered}</span><span class="stat-label">calls offered</span></div>
    <div class="stat"><span class="stat-value ${s.breachCount > 0 ? "warn" : ""}">${s.breachCount}</span><span class="stat-label">intervals below target</span></div>
    <div class="stat"><span class="stat-value">${s.worstSlPct.toFixed(2)}% @ ${s.worstInterval}</span><span class="stat-label">worst interval</span></div>
  `;
}

function drawTable(metrics: IntervalMetric[]): void {
  const tbody = el<HTMLTableSectionElement>("metricBody");
  tbody.innerHTML = "";
  for (const m of metrics) {
    const tr = document.createElement("tr");
    if (m.breach) {
      tr.className = "breach";
    }
    const coverageText =
      m.coverage === null ? "--" : m.coverage > 0 ? `+${m.coverage}` : String(m.coverage);
    const cells = [
      m.interval,
      String(m.offered),
      `${m.slPct.toFixed(2)}%`,
      `${m.abandonPct.toFixed(2)}%`,
      `${m.asaSeconds.toFixed(2)}s`,
      `${m.ahtSeconds.toFixed(2)}s`,
      `${m.occupancyPct.toFixed(2)}%`,
      m.requiredAgents === null ? "--" : String(m.requiredAgents),
      String(m.agentsScheduled),
      coverageText,
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

function render(): void {
  if (actualsRows.length === 0) {
    return;
  }
  const config = readConfig();
  if (!Number.isFinite(config.intervalMinutes) || config.intervalMinutes <= 0) {
    showError("Interval length must be a positive number of minutes.");
    return;
  }
  if (!(config.targetSlPct > 0 && config.targetSlPct <= 100)) {
    showError("Service-level target must be between 1 and 100.");
    return;
  }

  const metrics = computeMetrics(actualsRows, planMap, config);
  drawSummary(metrics, actualsRows);
  drawServiceLevel(metrics, config.targetSlPct);
  drawCoverage(metrics);
  drawTable(metrics);

  const planNote = planMap ? " Coverage is shown against the loaded staffing plan." : " Load a staffing plan to see coverage.";
  showInfo(`Charted ${metrics.length} intervals.${planNote}`);
}

function handleActuals(file: File): void {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      actualsRows = parseActualsCsv(String(reader.result));
      render();
    } catch (err) {
      actualsRows = [];
      showError(err instanceof Error ? err.message : "Could not read the file.");
    }
  };
  reader.onerror = () => showError("Could not read the file.");
  reader.readAsText(file);
}

function handlePlan(file: File): void {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      planMap = parsePlanCsv(String(reader.result));
      render();
    } catch (err) {
      planMap = null;
      showError(err instanceof Error ? err.message : "Could not read the plan file.");
    }
  };
  reader.onerror = () => showError("Could not read the plan file.");
  reader.readAsText(file);
}

function init(): void {
  el<HTMLInputElement>("actualsInput").addEventListener("change", (event) => {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      handleActuals(input.files[0]);
    }
  });
  el<HTMLInputElement>("planInput").addEventListener("change", (event) => {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      handlePlan(input.files[0]);
    }
  });
  ["intervalMinutes", "targetSlPct"].forEach((id) => {
    el<HTMLInputElement>(id).addEventListener("change", render);
  });
}

document.addEventListener("DOMContentLoaded", init);
