"use strict";
/*
 * DOM wiring and chart drawing for the MRR Movement Waterfall.
 *
 * This file is the only part that touches the page. It reads the ledger file,
 * calls the pure functions in movement.ts, draws the waterfall, fills the table,
 * and builds the downloadable movement CSV. No movement math lives here.
 */
const SVG_NS = "http://www.w3.org/2000/svg";
let currentMovement = [];
let annualize = false;
const money = new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});
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
/** A cent amount as CAD, annualized to ARR when the toggle is on. */
function fmt(cents) {
    const factor = annualize ? 12 : 1;
    return money.format((cents * factor) / 100);
}
function svgEl(name, attrs) {
    const node = document.createElementNS(SVG_NS, name);
    for (const [key, value] of Object.entries(attrs)) {
        node.setAttribute(key, String(value));
    }
    return node;
}
/** The six waterfall steps for one month, opening through closing. */
function stepsFor(row) {
    return [
        { label: "Opening", isTotal: true, amountCents: row.openingCents },
        { label: "New", isTotal: false, amountCents: row.newCents },
        { label: "Expansion", isTotal: false, amountCents: row.expansionCents },
        { label: "Contraction", isTotal: false, amountCents: -row.contractionCents },
        { label: "Churn", isTotal: false, amountCents: -row.churnedCents },
        { label: "Closing", isTotal: true, amountCents: row.closingCents },
    ];
}
/**
 * Waterfall chart for the selected month. Totals sit on the baseline; each delta
 * floats from the running total, green for a gain and red for a loss.
 */
function drawWaterfall(row) {
    const svg = el("chart");
    while (svg.firstChild) {
        svg.removeChild(svg.firstChild);
    }
    const width = 880;
    const height = 380;
    const margin = { top: 24, right: 24, bottom: 64, left: 72 };
    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const steps = stepsFor(row);
    const factor = annualize ? 12 : 1;
    // Scale spans zero to the highest running total, with a little headroom.
    let runningPeak = 0;
    let acc = 0;
    for (const s of steps) {
        if (s.isTotal) {
            acc = s.amountCents;
        }
        else {
            acc += s.amountCents;
        }
        runningPeak = Math.max(runningPeak, acc, s.isTotal ? s.amountCents : 0);
    }
    const maxVal = Math.max(1, runningPeak) * factor;
    const yOf = (cents) => plotH - (cents / maxVal) * plotH;
    const group = svgEl("g", { transform: `translate(${margin.left},${margin.top})` });
    svg.appendChild(group);
    // Gridlines and left axis labels.
    const ticks = 4;
    for (let t = 0; t <= ticks; t++) {
        const value = (maxVal / ticks) * t;
        const y = yOf(value);
        group.appendChild(svgEl("line", { x1: 0, y1: y, x2: plotW, y2: y, class: "grid" }));
        const label = svgEl("text", { x: -12, y: y + 4, class: "axis-label", "text-anchor": "end" });
        label.textContent = money.format(value / 100).replace(/\.00$/, "");
        group.appendChild(label);
    }
    const slotW = plotW / steps.length;
    const barW = Math.min(64, slotW * 0.6);
    let base = 0; // running total in cents, before the current step
    steps.forEach((s, i) => {
        const cx = i * slotW + slotW / 2;
        const amount = s.amountCents * factor;
        let top;
        let bottom;
        let cls;
        if (s.isTotal) {
            top = yOf(Math.max(0, amount));
            bottom = yOf(0);
            cls = "bar-total";
            base = s.amountCents;
        }
        else {
            const startVal = base * factor;
            const endVal = (base + s.amountCents) * factor;
            top = yOf(Math.max(startVal, endVal));
            bottom = yOf(Math.min(startVal, endVal));
            cls = s.amountCents >= 0 ? "bar-up" : "bar-down";
            base += s.amountCents;
        }
        const h = Math.max(1, bottom - top);
        group.appendChild(svgEl("rect", { x: cx - barW / 2, y: top, width: barW, height: h, class: cls }));
        // Value above each bar.
        const valLabel = svgEl("text", { x: cx, y: top - 6, class: "bar-value", "text-anchor": "middle" });
        const prefix = !s.isTotal && s.amountCents > 0 ? "+" : "";
        valLabel.textContent = `${prefix}${money.format(amount / 100).replace(/\.00$/, "")}`;
        group.appendChild(valLabel);
        // Step name below the axis.
        const xLabel = svgEl("text", { x: cx, y: plotH + 22, class: "axis-label", "text-anchor": "middle" });
        xLabel.textContent = s.label;
        group.appendChild(xLabel);
    });
}
function drawTable(rows) {
    const tbody = el("movementBody");
    tbody.innerHTML = "";
    for (const r of rows) {
        const tr = document.createElement("tr");
        const cells = [
            r.month,
            fmt(r.openingCents),
            fmt(r.newCents),
            fmt(r.expansionCents),
            fmt(r.contractionCents),
            fmt(r.churnedCents),
            fmt(r.closingCents),
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
function drawSummary(rows) {
    const last = rows[rows.length - 1];
    const first = rows[0];
    const netNew = last.closingCents - first.openingCents;
    const totalChurn = rows.reduce((sum, r) => sum + r.churnedCents, 0);
    el("summary").innerHTML = `
    <div class="stat"><span class="stat-value">${fmt(last.closingCents)}</span><span class="stat-label">closing ${annualize ? "ARR" : "MRR"} (${last.month})</span></div>
    <div class="stat"><span class="stat-value">${fmt(netNew)}</span><span class="stat-label">net change over ${rows.length} months</span></div>
    <div class="stat"><span class="stat-value">${fmt(totalChurn)}</span><span class="stat-label">churned across the period</span></div>
  `;
}
function fillMonthPicker(rows) {
    const select = el("monthPick");
    select.innerHTML = "";
    rows.forEach((r) => {
        const opt = document.createElement("option");
        opt.value = r.month;
        opt.textContent = r.month;
        select.appendChild(opt);
    });
    select.value = rows[rows.length - 1].month; // default to the latest month
}
function redraw() {
    if (currentMovement.length === 0) {
        return;
    }
    const month = el("monthPick").value;
    const row = currentMovement.find((r) => r.month === month) || currentMovement[currentMovement.length - 1];
    drawWaterfall(row);
    drawTable(currentMovement);
    drawSummary(currentMovement);
}
function handleFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
        try {
            const ledger = parseLedgerCsv(String(reader.result));
            currentMovement = computeMovement(ledger);
            fillMonthPicker(currentMovement);
            el("exportBtn").disabled = false;
            redraw();
            showInfo(`Loaded ${ledger.length} ledger rows across ${currentMovement.length} months. Pick a month to see its movement.`);
        }
        catch (err) {
            currentMovement = [];
            el("exportBtn").disabled = true;
            showError(err instanceof Error ? err.message : "Could not read the file.");
        }
    };
    reader.onerror = () => showError("Could not read the file.");
    reader.readAsText(file);
}
function exportMovement() {
    if (currentMovement.length === 0) {
        return;
    }
    const csv = toMovementCsv(currentMovement);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "mrr-movement.csv";
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
    el("monthPick").addEventListener("change", redraw);
    el("annualize").addEventListener("change", (event) => {
        annualize = event.target.checked;
        redraw();
    });
    el("exportBtn").addEventListener("click", exportMovement);
}
document.addEventListener("DOMContentLoaded", init);
