/*
 * DOM wiring and chart drawing for the PO/Invoice Compliance view.
 *
 * This file is the only part that touches the page. It reads the normalized
 * spend file, calls the pure functions in compliance.ts, draws the compliance
 * breakdown bar, fills the summary tiles and the flagged-lines table, and lists
 * the reasons each flagged line carries. No compliance math lives here.
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

function setMessage(message: string, kind: "info" | "error"): void {
  const box = el<HTMLDivElement>("message");
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

function drawSummary(summary: ComplianceSummary): void {
  el<HTMLDivElement>("summary").innerHTML = `
    <div class="stat"><span class="stat-value">${summary.compliantPct.toFixed(2)}%</span><span class="stat-label">lines fully compliant</span></div>
    <div class="stat"><span class="stat-value">${money(summary.offContractCents)}</span><span class="stat-label">off-contract spend (${summary.offContractLines} lines)</span></div>
    <div class="stat"><span class="stat-value">${money(summary.exceptionCents)}</span><span class="stat-label">match exceptions (${summary.exceptionLines} lines)</span></div>
    <div class="stat"><span class="stat-value">${money(summary.totalInvoiceCents)}</span><span class="stat-label">total invoiced</span></div>
  `;
}

/**
 * One horizontal bar split into three parts by line count: compliant, off-
 * contract, and match exceptions. A line that is both off-contract and an
 * exception counts once toward exceptions, so the three parts sum to the total.
 */
function drawBreakdown(summary: ComplianceSummary): void {
  const svg = el<HTMLElement>("breakdown") as unknown as SVGSVGElement;
  while (svg.firstChild) {
    svg.removeChild(svg.firstChild);
  }

  const width = 880;
  const height = 96;
  const margin = { left: 8, right: 8 };
  const barH = 48;
  const y = 16;
  const plotW = width - margin.left - margin.right;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const total = summary.totalLines || 1;
  // Off-contract and exception lines can overlap; exceptions take priority so
  // the segments never double-count.
  const exception = summary.exceptionLines;
  const offContractOnly = summary.flaggedLines - summary.exceptionLines;
  const compliant = summary.compliantLines;
  const segments = [
    { label: "Compliant", count: compliant, cls: "seg compliant" },
    { label: "Off-contract", count: offContractOnly, cls: "seg offcontract" },
    { label: "Exception", count: exception, cls: "seg exception" },
  ];

  let x = margin.left;
  for (const seg of segments) {
    const w = (seg.count / total) * plotW;
    if (seg.count > 0) {
      svg.appendChild(svgEl("rect", { x, y, width: Math.max(1, w), height: barH, class: seg.cls }));
      if (w > 70) {
        const label = document.createElementNS(SVG_NS, "text");
        label.setAttribute("x", String(x + w / 2));
        label.setAttribute("y", String(y + barH / 2 + 4));
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("class", "seg-label");
        label.textContent = `${seg.label} (${seg.count})`;
        svg.appendChild(label);
      }
    }
    x += w;
  }
}

function drawFlaggedTable(lines: ComplianceLine[]): void {
  const tbody = el<HTMLTableSectionElement>("flaggedBody");
  tbody.innerHTML = "";
  const flagged = flaggedOnly(lines);
  if (flagged.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 5;
    td.textContent = "No off-contract spend and no match exceptions. Every line is compliant.";
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }
  for (const l of flagged) {
    const tr = document.createElement("tr");
    tr.className = !l.matched ? "exception" : "offcontract";
    const id = document.createElement("td");
    id.textContent = `${l.lineId}  ${l.supplier}`;
    tr.appendChild(id);
    [money(l.poCents), money(l.receivedCents), money(l.invoiceCents)].forEach((v) => {
      const td = document.createElement("td");
      td.className = "num";
      td.textContent = v;
      tr.appendChild(td);
    });
    const reasons = document.createElement("td");
    reasons.textContent = l.reasons.join("; ");
    tr.appendChild(reasons);
    tbody.appendChild(tr);
  }
}

function render(text: string): void {
  const lines = parseAndJudge(text);
  const summary = summarize(lines);
  drawSummary(summary);
  drawBreakdown(summary);
  drawFlaggedTable(lines);
  setMessage(
    `Checked ${summary.totalLines} lines. ${summary.compliantLines} compliant, ${summary.offContractLines} off-contract, ${summary.exceptionLines} match exceptions.`,
    "info",
  );
}

function handleFile(file: File): void {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      render(String(reader.result));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not read the file.", "error");
    }
  };
  reader.onerror = () => setMessage("Could not read the file.", "error");
  reader.readAsText(file);
}

function init(): void {
  el<HTMLInputElement>("fileInput").addEventListener("change", (event) => {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      handleFile(input.files[0]);
    }
  });
}

document.addEventListener("DOMContentLoaded", init);
