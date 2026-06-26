"use strict";
/*
 * DOM wiring and grid drawing for the Loss Ratio Dashboard.
 *
 * This file is the only part that touches the page. It reads the clean-claims.csv
 * the funnel exports, calls the pure functions in lossratio.ts, and draws the
 * loss-ratio grid with its row, column, and overall totals. No ratio math lives
 * here.
 */
let currentRows = [];
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
function fmtMoney(cents) {
    return money.format(cents / 100);
}
/** Accent shade for a loss ratio: deeper as the ratio climbs toward and past 100%. */
function shadeFor(ratio) {
    const alpha = Math.min(0.9, 0.12 + ratio * 0.7);
    return `rgba(194, 96, 58, ${alpha.toFixed(3)})`;
}
/** A cell's tooltip: incurred over premium in plain dollars. */
function cellTitle(cell) {
    return `${fmtMoney(cell.incurredCents)} incurred / ${fmtMoney(cell.premiumCents)} premium`;
}
function drawGrid(grid) {
    const table = el("grid");
    table.innerHTML = "";
    // Header row: blank corner, one column per accident year, then a line total.
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    headRow.appendChild(th("Line \\ year"));
    for (const period of grid.periods) {
        headRow.appendChild(th(period));
    }
    headRow.appendChild(th("All years"));
    thead.appendChild(headRow);
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    for (const line of grid.lines) {
        const tr = document.createElement("tr");
        const head = document.createElement("th");
        head.scope = "row";
        head.textContent = line;
        tr.appendChild(head);
        for (const period of grid.periods) {
            const cell = grid.cells.get(`${line}|${period}`);
            tr.appendChild(cell ? ratioCell(cell) : emptyCell());
        }
        const lineTotal = grid.lineTotals.get(line);
        tr.appendChild(ratioCell(lineTotal, true));
        tbody.appendChild(tr);
    }
    // Footer row: per-year totals, then the book overall.
    const footRow = document.createElement("tr");
    footRow.className = "total-row";
    const footHead = document.createElement("th");
    footHead.scope = "row";
    footHead.textContent = "All lines";
    footRow.appendChild(footHead);
    for (const period of grid.periods) {
        footRow.appendChild(ratioCell(grid.periodTotals.get(period), true));
    }
    footRow.appendChild(ratioCell(grid.overall, true));
    tbody.appendChild(footRow);
    table.appendChild(tbody);
}
function th(text) {
    const node = document.createElement("th");
    node.textContent = text;
    return node;
}
function ratioCell(cell, isTotal = false) {
    const td = document.createElement("td");
    td.className = isTotal ? "cell total" : "cell";
    td.style.background = shadeFor(cell.ratio);
    td.title = cellTitle(cell);
    td.innerHTML = `<span class="ratio">${formatRatio(cell.ratio)}</span><span class="cents">${fmtMoney(cell.incurredCents)}</span>`;
    return td;
}
function emptyCell() {
    const td = document.createElement("td");
    td.className = "cell empty";
    td.textContent = "--";
    return td;
}
function drawSummary(grid) {
    const worst = bestOrWorst(grid, true);
    const best = bestOrWorst(grid, false);
    el("summary").innerHTML = `
    <div class="stat"><span class="stat-value">${formatRatio(grid.overall.ratio)}</span><span class="stat-label">overall loss ratio</span></div>
    <div class="stat"><span class="stat-value">${fmtMoney(grid.overall.incurredCents)}</span><span class="stat-label">incurred losses</span></div>
    <div class="stat"><span class="stat-value">${fmtMoney(grid.overall.premiumCents)}</span><span class="stat-label">earned premium</span></div>
    <div class="stat"><span class="stat-value">${worst.label}</span><span class="stat-label">highest cell at ${formatRatio(worst.ratio)}</span></div>
    <div class="stat"><span class="stat-value">${best.label}</span><span class="stat-label">lowest cell at ${formatRatio(best.ratio)}</span></div>
  `;
}
/** The line-and-year cell with the highest (or lowest) loss ratio. */
function bestOrWorst(grid, wantHighest) {
    let pick = null;
    for (const line of grid.lines) {
        for (const period of grid.periods) {
            const cell = grid.cells.get(`${line}|${period}`);
            if (!cell) {
                continue;
            }
            if (pick === null || (wantHighest ? cell.ratio > pick.ratio : cell.ratio < pick.ratio)) {
                pick = { label: `${line} ${period}`, ratio: cell.ratio };
            }
        }
    }
    return pick || { label: "--", ratio: 0 };
}
function redraw() {
    if (currentRows.length === 0) {
        return;
    }
    const grid = computeLossRatios(currentRows);
    drawGrid(grid);
    drawSummary(grid);
}
function handleFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
        try {
            const rows = parseCleanCsv(String(reader.result));
            currentRows = rows;
            redraw();
            const latest = rows.filter((r) => r.isLatest).length;
            showInfo(`Loaded ${rows.length} rows, ${latest} at the latest valuation. The grid shows the loss ratio per line and accident year.`);
        }
        catch (err) {
            currentRows = [];
            showError(err instanceof Error ? err.message : "Could not read the file.");
        }
    };
    reader.onerror = () => showError("Could not read the file.");
    reader.readAsText(file);
}
function init() {
    el("fileInput").addEventListener("change", (event) => {
        const input = event.target;
        if (input.files && input.files.length > 0) {
            handleFile(input.files[0]);
        }
    });
}
document.addEventListener("DOMContentLoaded", init);
