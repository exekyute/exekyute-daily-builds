"use strict";
/*
 * DOM wiring and chart drawing for the Cash Position Dashboard.
 *
 * This file is the only part that touches the page. It reads the movement file,
 * calls the pure functions in positions.ts, draws the closing-balance chart,
 * fills the table, and builds the downloadable closing-balances CSV. No cash
 * math lives here.
 */
const SVG_NS = "http://www.w3.org/2000/svg";
const cad = new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD" });
function money(cents) {
    return cad.format(cents / 100);
}
let currentPositions = [];
function el(id) {
    const node = document.getElementById(id);
    if (!node) {
        throw new Error(`Missing element #${id}`);
    }
    return node;
}
function showError(message) {
    const box = el("message");
    box.textContent = message;
    box.className = "message error";
}
function showInfo(message) {
    const box = el("message");
    box.textContent = message;
    box.className = "message info";
}
function svgEl(name, attrs) {
    const node = document.createElementNS(SVG_NS, name);
    for (const [key, value] of Object.entries(attrs)) {
        node.setAttribute(key, String(value));
    }
    return node;
}
/**
 * Bar chart of closing balance per account. Bars sit above or below a zero line
 * so an overdrawn account reads at a glance, and overdrawn bars take the danger
 * colour.
 */
function drawChart(positions) {
    const svg = el("chart");
    while (svg.firstChild) {
        svg.removeChild(svg.firstChild);
    }
    const width = 880;
    const height = 360;
    const margin = { top: 24, right: 24, bottom: 64, left: 88 };
    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const values = positions.map((p) => p.closingCents);
    const maxVal = Math.max(0, ...values);
    const minVal = Math.min(0, ...values);
    const span = maxVal - minVal || 1;
    const yOf = (cents) => plotH - ((cents - minVal) / span) * plotH;
    const group = svgEl("g", { transform: `translate(${margin.left},${margin.top})` });
    svg.appendChild(group);
    // Gridlines and left-axis labels in dollars.
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
    const slotW = plotW / positions.length;
    const barW = Math.min(72, slotW * 0.5);
    positions.forEach((p, i) => {
        const cx = i * slotW + slotW / 2;
        const top = yOf(Math.max(0, p.closingCents));
        const bottom = yOf(Math.min(0, p.closingCents));
        group.appendChild(svgEl("rect", {
            x: cx - barW / 2,
            y: top,
            width: barW,
            height: Math.max(1, bottom - top),
            class: p.overdrawn ? "bar overdrawn" : "bar",
        }));
        const label = svgEl("text", { x: cx, y: plotH + 22, class: "axis-label", "text-anchor": "middle" });
        label.textContent = p.account;
        group.appendChild(label);
    });
}
function drawTable(positions) {
    const tbody = el("positionBody");
    tbody.innerHTML = "";
    for (const p of positions) {
        const tr = document.createElement("tr");
        if (p.overdrawn) {
            tr.className = "flagged";
        }
        const account = document.createElement("td");
        account.textContent = p.account + (p.overdrawn ? "  (overdrawn)" : "");
        tr.appendChild(account);
        [p.openingCents, p.inflowCents, p.outflowCents, p.closingCents].forEach((cents) => {
            const td = document.createElement("td");
            td.className = "num";
            td.textContent = money(cents);
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    }
}
function drawSummary(summary) {
    el("summary").innerHTML = `
    <div class="stat"><span class="stat-value">${summary.accounts}</span><span class="stat-label">accounts as of ${summary.asOf}</span></div>
    <div class="stat"><span class="stat-value">${money(summary.inflowCents)}</span><span class="stat-label">total inflows</span></div>
    <div class="stat"><span class="stat-value">${money(summary.outflowCents)}</span><span class="stat-label">total outflows</span></div>
    <div class="stat"><span class="stat-value">${money(summary.closingCents)}</span><span class="stat-label">consolidated closing</span></div>
    <div class="stat"><span class="stat-value">${summary.overdrawnCount}</span><span class="stat-label">overdrawn accounts</span></div>
  `;
}
function render(text) {
    const movements = parsePositionCsv(text);
    currentPositions = computePositions(movements);
    const summary = summarize(currentPositions, movements);
    drawSummary(summary);
    drawChart(currentPositions);
    drawTable(currentPositions);
    el("exportBtn").disabled = false;
    const note = summary.overdrawnCount > 0
        ? `Built ${summary.accounts} account positions. ${summary.overdrawnCount} closed overdrawn and are flagged.`
        : `Built ${summary.accounts} account positions. None closed overdrawn.`;
    showInfo(note);
}
function handleFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
        try {
            render(String(reader.result));
        }
        catch (err) {
            currentPositions = [];
            el("exportBtn").disabled = true;
            showError(err instanceof Error ? err.message : "Could not read the file.");
        }
    };
    reader.onerror = () => showError("Could not read the file.");
    reader.readAsText(file);
}
function exportBalances() {
    if (currentPositions.length === 0) {
        return;
    }
    const csv = toClosingBalancesCsv(currentPositions);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "closing-balances.csv";
    link.click();
    URL.revokeObjectURL(url);
}
function init() {
    el("fileInput").addEventListener("change", (event) => {
        const input = event.target;
        if (input.files && input.files.length > 0) {
            handleFile(input.files[0]);
        }
    });
    el("exportBtn").addEventListener("click", exportBalances);
}
document.addEventListener("DOMContentLoaded", init);
