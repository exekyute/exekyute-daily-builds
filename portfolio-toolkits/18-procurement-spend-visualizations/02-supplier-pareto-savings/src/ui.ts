/*
 * DOM wiring and chart drawing for the Supplier Pareto and Savings Tracker.
 *
 * This file is the only part that touches the page. It reads the two files,
 * calls the pure functions in pareto.ts, draws the Pareto combo chart and the
 * savings chart, and fills the tables. No spend or savings math lives here.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

const cad = new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD" });
function money(cents: number): string {
  return cad.format(cents / 100);
}

function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) {
    throw new Error(`Missing element #${id}`);
  }
  return node as T;
}

function setMessage(id: string, message: string, kind: "info" | "error"): void {
  const box = el<HTMLDivElement>(id);
  box.textContent = message;
  box.className = `message ${kind}`;
}

function svgEl(name: string, attrs: Record<string, string | number>): SVGElement {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) {
    node.setAttribute(key, String(value));
  }
  return node;
}

function clearSvg(svg: SVGSVGElement): void {
  while (svg.firstChild) {
    svg.removeChild(svg.firstChild);
  }
}

/**
 * Pareto combo chart: spend bars sorted high to low, with a cumulative-share
 * line over them and a dashed line at the 80 percent cut. Vital-few bars take
 * the accent colour, the long tail takes the soft colour.
 */
function drawParetoChart(result: ParetoResult): void {
  const svg = el<HTMLElement>("paretoChart") as unknown as SVGSVGElement;
  clearSvg(svg);

  const width = 880;
  const height = 380;
  const margin = { top: 24, right: 56, bottom: 72, left: 88 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const rows = result.rows;
  const maxVal = Math.max(1, ...rows.map((r) => r.cents));
  const group = svgEl("g", { transform: `translate(${margin.left},${margin.top})` });
  svg.appendChild(group);

  // Left axis: dollar gridlines.
  const ticks = 4;
  for (let t = 0; t <= ticks; t++) {
    const value = (maxVal / ticks) * t;
    const y = plotH - (value / maxVal) * plotH;
    group.appendChild(svgEl("line", { x1: 0, y1: y, x2: plotW, y2: y, class: "grid" }));
    const label = svgEl("text", { x: -10, y: y + 4, class: "axis-label", "text-anchor": "end" });
    label.textContent = cad.format(value / 100);
    group.appendChild(label);
  }

  // Right axis: the 80 percent cut.
  const cutY = plotH - (PARETO_THRESHOLD / 100) * plotH;
  group.appendChild(svgEl("line", { x1: 0, y1: cutY, x2: plotW, y2: cutY, class: "cut-line" }));
  const cutLabel = svgEl("text", { x: plotW + 8, y: cutY + 4, class: "axis-label" });
  cutLabel.textContent = `${PARETO_THRESHOLD}%`;
  group.appendChild(cutLabel);

  const slotW = plotW / rows.length;
  const barW = Math.min(70, slotW * 0.6);

  rows.forEach((r, i) => {
    const cx = i * slotW + slotW / 2;
    const barH = (r.cents / maxVal) * plotH;
    group.appendChild(
      svgEl("rect", { x: cx - barW / 2, y: plotH - barH, width: barW, height: Math.max(1, barH), rx: 3, class: r.vitalFew ? "bar vital" : "bar tail" }),
    );
    const label = svgEl("text", { x: cx, y: plotH + 20, class: "axis-label", "text-anchor": "middle" });
    label.textContent = r.supplier;
    group.appendChild(label);
  });

  // Cumulative-share line and points, scaled 0 to 100 percent over plot height.
  const points = rows.map((r, i) => {
    const cx = i * slotW + slotW / 2;
    const y = plotH - (r.cumulativePct / 100) * plotH;
    return `${cx},${y}`;
  });
  group.appendChild(svgEl("polyline", { points: points.join(" "), class: "cum-line" }));
  rows.forEach((r, i) => {
    const cx = i * slotW + slotW / 2;
    const y = plotH - (r.cumulativePct / 100) * plotH;
    group.appendChild(svgEl("circle", { cx, cy: y, r: 4, class: "cum-point" }));
    const label = svgEl("text", { x: cx, y: y - 10, class: "cum-label", "text-anchor": "middle" });
    label.textContent = `${r.cumulativePct.toFixed(1)}%`;
    group.appendChild(label);
  });
}

function drawParetoTable(result: ParetoResult): void {
  const tbody = el<HTMLTableSectionElement>("paretoBody");
  tbody.innerHTML = "";
  for (const r of result.rows) {
    const tr = document.createElement("tr");
    if (r.vitalFew) {
      tr.className = "vital";
    }
    const name = document.createElement("td");
    name.textContent = r.supplier + (r.vitalFew ? "  (vital few)" : "");
    tr.appendChild(name);
    [money(r.cents), `${r.pct.toFixed(2)}%`, `${r.cumulativePct.toFixed(2)}%`].forEach((v) => {
      const td = document.createElement("td");
      td.className = "num";
      td.textContent = v;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }
}

function drawParetoSummary(result: ParetoResult): void {
  el<HTMLDivElement>("paretoSummary").innerHTML = `
    <div class="stat"><span class="stat-value">${money(result.totalCents)}</span><span class="stat-label">total spend</span></div>
    <div class="stat"><span class="stat-value">${result.supplierCount}</span><span class="stat-label">suppliers</span></div>
    <div class="stat"><span class="stat-value">${result.vitalFewCount}</span><span class="stat-label">vital-few suppliers</span></div>
    <div class="stat"><span class="stat-value">${result.vitalFewPct.toFixed(2)}%</span><span class="stat-label">of spend from the vital few</span></div>
  `;
}

function renderPareto(text: string): void {
  const result = buildPareto(parseNormalizedCsv(text));
  drawParetoSummary(result);
  drawParetoChart(result);
  drawParetoTable(result);
  setMessage("paretoMessage", `Ranked ${result.supplierCount} suppliers. ${result.vitalFewCount} make up ${result.vitalFewPct.toFixed(2)} percent of spend.`, "info");
}

/** Savings chart: target and realized bars side by side per initiative. */
function drawSavingsChart(result: SavingsResult): void {
  const svg = el<HTMLElement>("savingsChart") as unknown as SVGSVGElement;
  clearSvg(svg);

  const rows = result.rows;
  const width = 880;
  const height = 360;
  const margin = { top: 24, right: 24, bottom: 72, left: 88 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const maxVal = Math.max(1, ...rows.map((r) => Math.max(r.targetCents, r.realizedCents)));
  const minVal = Math.min(0, ...rows.map((r) => r.realizedCents));
  const span = maxVal - minVal || 1;
  const yOf = (cents: number): number => plotH - ((cents - minVal) / span) * plotH;

  const group = svgEl("g", { transform: `translate(${margin.left},${margin.top})` });
  svg.appendChild(group);

  const ticks = 4;
  for (let t = 0; t <= ticks; t++) {
    const value = minVal + (span / ticks) * t;
    const y = yOf(value);
    group.appendChild(svgEl("line", { x1: 0, y1: y, x2: plotW, y2: y, class: "grid" }));
    const label = svgEl("text", { x: -10, y: y + 4, class: "axis-label", "text-anchor": "end" });
    label.textContent = cad.format(value / 100);
    group.appendChild(label);
  }
  const zeroY = yOf(0);
  group.appendChild(svgEl("line", { x1: 0, y1: zeroY, x2: plotW, y2: zeroY, class: "zero-line" }));

  const slotW = plotW / rows.length;
  const barW = Math.min(28, slotW * 0.28);

  rows.forEach((r, i) => {
    const cx = i * slotW + slotW / 2;
    // Target bar (soft outline) on the left, realized bar on the right.
    const tTop = yOf(Math.max(0, r.targetCents));
    const tBot = yOf(Math.min(0, r.targetCents));
    group.appendChild(svgEl("rect", { x: cx - barW - 2, y: tTop, width: barW, height: Math.max(1, tBot - tTop), rx: 3, class: "bar target" }));

    const rTop = yOf(Math.max(0, r.realizedCents));
    const rBot = yOf(Math.min(0, r.realizedCents));
    group.appendChild(svgEl("rect", { x: cx + 2, y: rTop, width: barW, height: Math.max(1, rBot - rTop), rx: 3, class: r.met ? "bar met" : "bar missed" }));

    const label = svgEl("text", { x: cx, y: plotH + 20, class: "axis-label", "text-anchor": "middle" });
    label.textContent = r.id;
    group.appendChild(label);
    const cat = svgEl("text", { x: cx, y: plotH + 36, class: "axis-sub", "text-anchor": "middle" });
    cat.textContent = r.category;
    group.appendChild(cat);
  });
}

function drawSavingsTable(result: SavingsResult): void {
  const tbody = el<HTMLTableSectionElement>("savingsBody");
  tbody.innerHTML = "";
  for (const r of result.rows) {
    const tr = document.createElement("tr");
    if (!r.met) {
      tr.className = "flagged";
    }
    const name = document.createElement("td");
    name.textContent = `${r.id}  ${r.category}`;
    tr.appendChild(name);
    const att = r.attainmentPct === null ? "n/a" : `${r.attainmentPct.toFixed(2)}%`;
    [money(r.targetCents), money(r.realizedCents), att].forEach((v) => {
      const td = document.createElement("td");
      td.className = "num";
      td.textContent = v;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }
}

function drawSavingsSummary(result: SavingsResult): void {
  const att = result.overallAttainmentPct === null ? "n/a" : `${result.overallAttainmentPct.toFixed(2)}%`;
  el<HTMLDivElement>("savingsSummary").innerHTML = `
    <div class="stat"><span class="stat-value">${money(result.totalTargetCents)}</span><span class="stat-label">target savings</span></div>
    <div class="stat"><span class="stat-value">${money(result.totalRealizedCents)}</span><span class="stat-label">realized savings</span></div>
    <div class="stat"><span class="stat-value">${att}</span><span class="stat-label">overall attainment</span></div>
    <div class="stat"><span class="stat-value">${result.rows.filter((r) => r.met).length} / ${result.rows.length}</span><span class="stat-label">initiatives at or above target</span></div>
  `;
}

function drawSavingsWarnings(warnings: Warning[]): void {
  const panel = el<HTMLDivElement>("savingsWarnings");
  if (warnings.length === 0) {
    panel.style.display = "none";
    panel.innerHTML = "";
    return;
  }
  panel.style.display = "block";
  panel.innerHTML = `<h3>Review notes</h3><ul>${warnings.map((w) => `<li>${w.message}</li>`).join("")}</ul>`;
}

function renderSavings(text: string): void {
  const result = parseSavingsCsv(text);
  drawSavingsSummary(result);
  drawSavingsChart(result);
  drawSavingsTable(result);
  drawSavingsWarnings(result.warnings);
  const att = result.overallAttainmentPct === null ? "no target set" : `${result.overallAttainmentPct.toFixed(2)} percent of target`;
  setMessage("savingsMessage", `Tracked ${result.rows.length} initiatives, realizing ${att}.`, "info");
}

function wireInput(inputId: string, messageId: string, render: (text: string) => void): void {
  el<HTMLInputElement>(inputId).addEventListener("change", (event) => {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) {
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      try {
        render(String(reader.result));
      } catch (err) {
        setMessage(messageId, err instanceof Error ? err.message : "Could not read the file.", "error");
      }
    };
    reader.onerror = () => setMessage(messageId, "Could not read the file.", "error");
    reader.readAsText(input.files[0]);
  });
}

function init(): void {
  wireInput("paretoFile", "paretoMessage", renderPareto);
  wireInput("savingsFile", "savingsMessage", (text) => renderSavings(text));
}

document.addEventListener("DOMContentLoaded", init);
