"use strict";
/*
 * DOM wiring and heatmap drawing for the Cohort Retention Heatmap.
 *
 * This file is the only part that touches the page. It reads the ledger file,
 * calls the pure functions in cohort.ts, draws the heatmap grid, fills the
 * summary, and builds the downloadable cohort CSV. No retention math lives here.
 */
let currentCohorts = [];
let mode = "revenue";
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
/** Background for a cell, the accent hue deepening with retention. */
function cellColor(pct) {
    // 100% sits near full strength; expansion above 100% stays at full strength.
    const t = Math.max(0.06, Math.min(1, pct / 100));
    return `rgba(47, 111, 158, ${t.toFixed(3)})`;
}
/** Black or white text, whichever reads on the cell colour. */
function textColor(pct) {
    return pct / 100 > 0.55 ? "#ffffff" : "#1f2a44";
}
function drawHeatmap() {
    const grid = el("heatmap");
    grid.innerHTML = "";
    if (currentCohorts.length === 0) {
        return;
    }
    const width = currentCohorts[0].cells.length;
    grid.style.gridTemplateColumns = `140px repeat(${width}, 1fr)`;
    // Header row: a corner label then "Month 0", "Month 1", ...
    const corner = document.createElement("div");
    corner.className = "hm-corner";
    corner.textContent = mode === "revenue" ? "Revenue retained" : "Logos retained";
    grid.appendChild(corner);
    for (let offset = 0; offset < width; offset++) {
        const head = document.createElement("div");
        head.className = "hm-head";
        head.textContent = `M${offset}`;
        grid.appendChild(head);
    }
    for (const s of currentCohorts) {
        const rowLabel = document.createElement("div");
        rowLabel.className = "hm-rowlabel";
        rowLabel.innerHTML = `<span class="hm-cohort">${s.cohort}</span><span class="hm-sub">${s.cohortSize} customers, ${money.format(s.startCents / 100)}</span>`;
        grid.appendChild(rowLabel);
        for (const cell of s.cells) {
            const box = document.createElement("div");
            box.className = "hm-cell";
            if (!cell.hasData) {
                box.classList.add("hm-blank");
                grid.appendChild(box);
                continue;
            }
            const pct = mode === "revenue" ? cell.revenuePct : cell.logoPct;
            box.style.background = cellColor(pct);
            box.style.color = textColor(pct);
            box.textContent = `${Math.round(pct)}%`;
            const detail = mode === "revenue"
                ? `${s.cohort} month ${cell.offset}: ${money.format(cell.retainedCents / 100)} of ${money.format(s.startCents / 100)} (${cell.revenuePct.toFixed(2)}%)`
                : `${s.cohort} month ${cell.offset}: ${cell.activeLogos} of ${s.cohortSize} customers (${cell.logoPct.toFixed(2)}%)`;
            box.title = detail;
            grid.appendChild(box);
        }
    }
}
function drawSummary() {
    const totalStart = currentCohorts.reduce((sum, s) => sum + s.startCents, 0);
    const totalCustomers = currentCohorts.reduce((sum, s) => sum + s.cohortSize, 0);
    el("summary").innerHTML = `
    <div class="stat"><span class="stat-value">${currentCohorts.length}</span><span class="stat-label">signup cohorts</span></div>
    <div class="stat"><span class="stat-value">${totalCustomers}</span><span class="stat-label">customers tracked</span></div>
    <div class="stat"><span class="stat-value">${money.format(totalStart / 100)}</span><span class="stat-label">starting MRR across cohorts</span></div>
  `;
}
function redraw() {
    drawHeatmap();
    drawSummary();
}
function handleFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
        try {
            const ledger = parseLedgerCsv(String(reader.result));
            currentCohorts = computeCohorts(ledger);
            el("exportBtn").disabled = false;
            redraw();
            showInfo(`Loaded ${ledger.length} ledger rows into ${currentCohorts.length} cohorts. Darker cells held more of their starting base.`);
        }
        catch (err) {
            currentCohorts = [];
            el("exportBtn").disabled = true;
            el("heatmap").innerHTML = "";
            showError(err instanceof Error ? err.message : "Could not read the file.");
        }
    };
    reader.onerror = () => showError("Could not read the file.");
    reader.readAsText(file);
}
function exportCohorts() {
    if (currentCohorts.length === 0) {
        return;
    }
    const csv = toCohortCsv(currentCohorts);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "cohort-retention.csv";
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
    el("modePick").addEventListener("change", (event) => {
        mode = event.target.value === "logo" ? "logo" : "revenue";
        if (currentCohorts.length > 0) {
            redraw();
        }
    });
    el("exportBtn").addEventListener("click", exportCohorts);
}
document.addEventListener("DOMContentLoaded", init);
