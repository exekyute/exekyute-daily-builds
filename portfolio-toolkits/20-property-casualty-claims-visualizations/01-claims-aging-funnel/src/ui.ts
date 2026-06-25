/*
 * DOM wiring and chart drawing for the Claims Aging and Status Funnel.
 *
 * This file is the only part that touches the page. It reads the register file,
 * calls the pure functions in aging.ts, draws the aging funnel, fills the status
 * and bucket tables, and builds the downloadable clean-claims CSV. No aging math
 * lives here.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

let currentRows: RegisterRow[] = [];

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

function fmtMoney(cents: number): string {
  return money.format(cents / 100);
}

function svgEl(name: string, attrs: Record<string, string | number>): SVGElement {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) {
    node.setAttribute(key, String(value));
  }
  return node;
}

/**
 * Aging funnel: one horizontal bar per age bucket, widest where the most open
 * claims sit, oldest at the bottom. Each bar is labelled with its claim count.
 */
function drawFunnel(summary: AgingSummary): void {
  const svg = el<HTMLElement>("chart") as unknown as SVGSVGElement;
  while (svg.firstChild) {
    svg.removeChild(svg.firstChild);
  }

  const width = 880;
  const rowH = 56;
  const gap = 12;
  const margin = { top: 16, right: 96, bottom: 16, left: 96 };
  const buckets = summary.buckets;
  const height = margin.top + margin.bottom + buckets.length * rowH + (buckets.length - 1) * gap;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const plotW = width - margin.left - margin.right;
  const maxCount = Math.max(1, ...buckets.map((b) => b.count));

  buckets.forEach((bucket, i) => {
    const y = margin.top + i * (rowH + gap);
    const barW = (bucket.count / maxCount) * plotW;
    const cx = margin.left + plotW / 2;

    // Bucket label on the left.
    const label = svgEl("text", { x: margin.left - 16, y: y + rowH / 2 + 5, class: "funnel-label", "text-anchor": "end" });
    label.textContent = `${bucket.label} days`;
    svg.appendChild(label);

    // Centred funnel bar.
    svg.appendChild(
      svgEl("rect", {
        x: cx - barW / 2,
        y,
        width: Math.max(bucket.count === 0 ? 0 : 2, barW),
        height: rowH,
        rx: 6,
        class: bucket.count === 0 ? "funnel-bar empty" : "funnel-bar",
      }),
    );

    // Count on the right.
    const count = svgEl("text", { x: width - margin.right + 16, y: y + rowH / 2 + 5, class: "funnel-count", "text-anchor": "start" });
    count.textContent = `${bucket.count} ${bucket.count === 1 ? "claim" : "claims"}`;
    svg.appendChild(count);
  });
}

function drawSummary(summary: AgingSummary): void {
  const s = summary.statusCounts;
  const avg = summary.avgDaysToClose === null ? "n/a" : `${summary.avgDaysToClose} days`;
  el<HTMLDivElement>("summary").innerHTML = `
    <div class="stat"><span class="stat-value">${summary.totalClaims}</span><span class="stat-label">claims as of ${summary.asOf}</span></div>
    <div class="stat"><span class="stat-value">${s.open} / ${s.pending} / ${s.closed}</span><span class="stat-label">open / pending / closed</span></div>
    <div class="stat"><span class="stat-value">${avg}</span><span class="stat-label">average days to close</span></div>
    <div class="stat"><span class="stat-value">${fmtMoney(summary.totalIncurredCents)}</span><span class="stat-label">incurred at latest valuation</span></div>
    <div class="stat"><span class="stat-value">${fmtMoney(summary.totalPaidCents)}</span><span class="stat-label">paid at latest valuation</span></div>
  `;
}

function drawBucketTable(summary: AgingSummary): void {
  const tbody = el<HTMLTableSectionElement>("bucketBody");
  tbody.innerHTML = "";
  const openInventory = summary.buckets.reduce((sum, b) => sum + b.count, 0);
  for (const bucket of summary.buckets) {
    const tr = document.createElement("tr");
    const share = openInventory === 0 ? "0%" : `${Math.round((bucket.count / openInventory) * 100)}%`;
    const cells = [`${bucket.label} days`, String(bucket.count), share];
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

function redraw(): void {
  if (currentRows.length === 0) {
    return;
  }
  const summary = summarize(currentRows);
  drawFunnel(summary);
  drawSummary(summary);
  drawBucketTable(summary);
}

function handleFile(file: File): void {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const rows = parseRegisterCsv(String(reader.result));
      currentRows = rows;
      el<HTMLButtonElement>("exportBtn").disabled = false;
      redraw();
      const summary = summarize(rows);
      showInfo(`Loaded ${rows.length} valuation rows across ${summary.totalClaims} claims, valued as of ${summary.asOf}.`);
    } catch (err) {
      currentRows = [];
      el<HTMLButtonElement>("exportBtn").disabled = true;
      showError(err instanceof Error ? err.message : "Could not read the file.");
    }
  };
  reader.onerror = () => showError("Could not read the file.");
  reader.readAsText(file);
}

function exportClean(): void {
  if (currentRows.length === 0) {
    return;
  }
  const csv = toCleanCsv(currentRows);
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "clean-claims.csv";
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
  el<HTMLButtonElement>("exportBtn").addEventListener("click", exportClean);
}

document.addEventListener("DOMContentLoaded", init);
