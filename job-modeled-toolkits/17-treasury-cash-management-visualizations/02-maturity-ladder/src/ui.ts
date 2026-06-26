/*
 * DOM wiring and chart drawing for the Maturity Ladder.
 *
 * This file is the only part that touches the page. It reads the obligations
 * file, calls the pure functions in ladder.ts, draws the ladder, fills the
 * table, and builds the downloadable maturities-by-week CSV. No bucketing math
 * lives here.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

const cad = new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD" });
function money(cents: number): string {
  return cad.format(cents / 100);
}

let loadedObligations: Obligation[] = [];

function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) {
    throw new Error(`Missing element #${id}`);
  }
  return node as T;
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

function readAsOf(): string {
  return el<HTMLInputElement>("asOf").value;
}

function readThresholdCents(): number {
  const raw = el<HTMLInputElement>("threshold").value.trim();
  if (!/^\d+(\.\d{1,2})?$/.test(raw)) {
    throw new Error("Concentration threshold must be a dollar figure of zero or more.");
  }
  const [whole, frac = ""] = raw.split(".");
  return Number(whole) * 100 + Number(frac.padEnd(2, "0"));
}

/** Bar chart of the ladder: one rung per bucket, heavy and overdue rungs flagged. */
function drawChart(buckets: Bucket[]): void {
  const svg = el<HTMLElement>("chart") as unknown as SVGSVGElement;
  while (svg.firstChild) {
    svg.removeChild(svg.firstChild);
  }

  const width = 880;
  const height = 360;
  const margin = { top: 24, right: 24, bottom: 56, left: 88 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;

  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const maxVal = Math.max(1, ...buckets.map((b) => b.totalCents));
  const yOf = (cents: number): number => plotH - (cents / maxVal) * plotH;

  const group = svgEl("g", { transform: `translate(${margin.left},${margin.top})` });
  svg.appendChild(group);

  const ticks = 4;
  for (let t = 0; t <= ticks; t++) {
    const value = (maxVal / ticks) * t;
    const y = yOf(value);
    group.appendChild(svgEl("line", { x1: 0, y1: y, x2: plotW, y2: y, class: "grid" }));
    const label = svgEl("text", { x: -10, y: y + 4, class: "axis-label", "text-anchor": "end" });
    label.textContent = cad.format(value / 100);
    group.appendChild(label);
  }

  const slotW = plotW / buckets.length;
  const barW = Math.min(40, slotW * 0.62);

  buckets.forEach((b, i) => {
    const cx = i * slotW + slotW / 2;
    const y = yOf(b.totalCents);
    let cls = "bar";
    if (b.kind === "overdue" && b.totalCents > 0) {
      cls = "bar overdue";
    } else if (b.heavy) {
      cls = "bar heavy";
    }
    group.appendChild(svgEl("rect", { x: cx - barW / 2, y, width: barW, height: Math.max(0, plotH - y), class: cls }));
    const label = svgEl("text", { x: cx, y: plotH + 20, class: "axis-label", "text-anchor": "middle" });
    label.textContent = b.label;
    group.appendChild(label);
  });
}

function drawTable(buckets: Bucket[]): void {
  const tbody = el<HTMLTableSectionElement>("ladderBody");
  tbody.innerHTML = "";
  for (const b of buckets) {
    if (b.count === 0) {
      continue;
    }
    const tr = document.createElement("tr");
    if ((b.kind === "overdue") || b.heavy) {
      tr.className = "flagged";
    }
    const tag = b.kind === "overdue" ? "  (overdue)" : b.heavy ? "  (heavy)" : "";
    const cells = [b.label + tag, b.startDate || "--", String(b.count), money(b.totalCents)];
    cells.forEach((value, idx) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (idx >= 2) {
        td.className = "num";
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }
}

function drawSummary(summary: LadderSummary, asOf: string): void {
  el<HTMLDivElement>("summary").innerHTML = `
    <div class="stat"><span class="stat-value">${summary.obligations}</span><span class="stat-label">obligations as of ${asOf}</span></div>
    <div class="stat"><span class="stat-value">${money(summary.within13Cents)}</span><span class="stat-label">due within 13 weeks</span></div>
    <div class="stat"><span class="stat-value">${money(summary.overdueCents)}</span><span class="stat-label">overdue (${summary.overdueCount})</span></div>
    <div class="stat"><span class="stat-value">${summary.peakLabel}: ${money(summary.peakCents)}</span><span class="stat-label">heaviest rung</span></div>
  `;
}

function render(): void {
  const asOf = readAsOf();
  if (!asOf) {
    showError("Choose an as-of date.");
    return;
  }
  let thresholdCents: number;
  try {
    thresholdCents = readThresholdCents();
  } catch (err) {
    showError(err instanceof Error ? err.message : "Bad threshold.");
    return;
  }

  const buckets = buildLadder(loadedObligations, asOf, thresholdCents);
  drawSummary(summarize(buckets), asOf);
  drawChart(buckets);
  drawTable(buckets);
  el<HTMLButtonElement>("exportBtn").disabled = false;
  const overdue = buckets.find((b) => b.kind === "overdue")!;
  const note =
    overdue.count > 0
      ? `Bucketed ${loadedObligations.length} obligations. ${overdue.count} overdue, folded into week 1 on export.`
      : `Bucketed ${loadedObligations.length} obligations. None overdue.`;
  showInfo(note);
}

function handleFile(file: File): void {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      loadedObligations = parseObligationCsv(String(reader.result));
      render();
    } catch (err) {
      loadedObligations = [];
      el<HTMLButtonElement>("exportBtn").disabled = true;
      showError(err instanceof Error ? err.message : "Could not read the file.");
    }
  };
  reader.onerror = () => showError("Could not read the file.");
  reader.readAsText(file);
}

function exportMaturities(): void {
  if (loadedObligations.length === 0) {
    return;
  }
  const csv = toMaturitiesByWeekCsv(loadedObligations, readAsOf());
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "maturities-by-week.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function init(): void {
  el<HTMLInputElement>("fileInput").addEventListener("change", (event) => {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      handleFile(input.files[0]);
    }
  });
  ["asOf", "threshold"].forEach((id) => {
    el<HTMLInputElement>(id).addEventListener("change", () => {
      if (loadedObligations.length > 0) {
        render();
      }
    });
  });
  el<HTMLButtonElement>("exportBtn").addEventListener("click", exportMaturities);
}

document.addEventListener("DOMContentLoaded", init);
