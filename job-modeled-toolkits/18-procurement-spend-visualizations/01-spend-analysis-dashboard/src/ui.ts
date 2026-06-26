/*
 * DOM wiring and chart drawing for the Spend Analysis Dashboard.
 *
 * This file is the only part that touches the page. It reads the spend-lines
 * file, calls the pure functions in spend.ts, draws the category and supplier
 * bar charts, fills the tables and the warnings panel, and builds the
 * downloadable normalized CSV. No spend math lives here.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

const cad = new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD" });
function money(cents: number): string {
  return cad.format(cents / 100);
}

let currentLines: SpendLine[] = [];

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

interface BarRow {
  label: string;
  cents: number;
  pct: number;
  flagged: boolean;
}

/**
 * Horizontal bar chart of spend by row, largest at the top. Flagged rows take
 * the danger colour so an unrecognized category reads at a glance.
 */
function drawBars(svgId: string, rows: BarRow[]): void {
  const svg = el<HTMLElement>(svgId) as unknown as SVGSVGElement;
  while (svg.firstChild) {
    svg.removeChild(svg.firstChild);
  }

  const width = 880;
  const rowH = 40;
  const margin = { top: 16, right: 150, bottom: 16, left: 200 };
  const plotW = width - margin.left - margin.right;
  const height = margin.top + margin.bottom + rows.length * rowH;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const maxVal = Math.max(1, ...rows.map((r) => r.cents));
  const group = svgEl("g", { transform: `translate(${margin.left},${margin.top})` });
  svg.appendChild(group);

  rows.forEach((r, i) => {
    const y = i * rowH;
    const barH = rowH * 0.6;
    const barW = Math.max(1, (r.cents / maxVal) * plotW);

    const name = svgEl("text", { x: -12, y: y + barH / 2 + 4, class: "axis-label", "text-anchor": "end" });
    name.textContent = r.label;
    group.appendChild(name);

    group.appendChild(
      svgEl("rect", { x: 0, y, width: barW, height: barH, rx: 4, class: r.flagged ? "bar flagged" : "bar" }),
    );

    const value = svgEl("text", { x: barW + 10, y: y + barH / 2 + 4, class: "bar-value" });
    value.textContent = `${money(r.cents)}  (${r.pct.toFixed(2)}%)`;
    group.appendChild(value);
  });
}

function drawTable(bodyId: string, rows: BarRow[], firstHeader: string): void {
  const tbody = el<HTMLTableSectionElement>(bodyId);
  tbody.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    if (r.flagged) {
      tr.className = "flagged";
    }
    const label = document.createElement("td");
    label.textContent = r.label + (r.flagged ? "  (not in taxonomy)" : "");
    tr.appendChild(label);
    const cents = document.createElement("td");
    cents.className = "num";
    cents.textContent = money(r.cents);
    tr.appendChild(cents);
    const pct = document.createElement("td");
    pct.className = "num";
    pct.textContent = `${r.pct.toFixed(2)}%`;
    tr.appendChild(pct);
    tbody.appendChild(tr);
  }
  void firstHeader;
}

function drawSummary(summary: SpendSummary): void {
  el<HTMLDivElement>("summary").innerHTML = `
    <div class="stat"><span class="stat-value">${money(summary.totalCents)}</span><span class="stat-label">total spend</span></div>
    <div class="stat"><span class="stat-value">${summary.supplierCount}</span><span class="stat-label">suppliers</span></div>
    <div class="stat"><span class="stat-value">${summary.categoryCount}</span><span class="stat-label">categories</span></div>
    <div class="stat"><span class="stat-value">${money(summary.offContractCents)}</span><span class="stat-label">off-contract spend</span></div>
    <div class="stat"><span class="stat-value">${summary.flaggedCount}</span><span class="stat-label">flagged lines</span></div>
  `;
}

function drawWarnings(warnings: Warning[]): void {
  const panel = el<HTMLDivElement>("warnings");
  if (warnings.length === 0) {
    panel.style.display = "none";
    panel.innerHTML = "";
    return;
  }
  panel.style.display = "block";
  const items = warnings.map((w) => `<li class="warn-${w.kind}">${w.message}</li>`).join("");
  panel.innerHTML = `<h3>Review notes</h3><ul>${items}</ul>`;
}

function render(text: string): void {
  const { lines, warnings } = parseSpendCsv(text);
  currentLines = lines;
  const summary = summarize(lines, warnings);
  drawSummary(summary);

  const categoryRows: BarRow[] = totalsByCategory(lines).map((c) => ({ label: c.category, cents: c.cents, pct: c.pct, flagged: !c.known }));
  const supplierRows: BarRow[] = totalsBySupplier(lines).map((s) => ({ label: s.supplier, cents: s.cents, pct: s.pct, flagged: false }));

  drawBars("categoryChart", categoryRows);
  drawBars("supplierChart", supplierRows);
  drawTable("categoryBody", categoryRows, "Category");
  drawTable("supplierBody", supplierRows, "Supplier");
  drawWarnings(warnings);

  el<HTMLButtonElement>("exportBtn").disabled = false;
  const note = `Analyzed ${summary.lineCount} clean lines totalling ${money(summary.totalCents)}.` +
    (warnings.length > 0 ? ` ${warnings.length} review note${warnings.length === 1 ? "" : "s"} below.` : "");
  showInfo(note);
}

function handleFile(file: File): void {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      render(String(reader.result));
    } catch (err) {
      currentLines = [];
      el<HTMLButtonElement>("exportBtn").disabled = true;
      drawWarnings([]);
      showError(err instanceof Error ? err.message : "Could not read the file.");
    }
  };
  reader.onerror = () => showError("Could not read the file.");
  reader.readAsText(file);
}

function exportNormalized(): void {
  if (currentLines.length === 0) {
    return;
  }
  const csv = toNormalizedCsv(currentLines);
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "normalized-spend.csv";
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
  el<HTMLButtonElement>("exportBtn").addEventListener("click", exportNormalized);
}

document.addEventListener("DOMContentLoaded", init);
