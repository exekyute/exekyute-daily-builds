"use strict";
/*
 * DOM wiring and chart drawing for the Liquidity Forecast.
 *
 * This file is the only part that touches the page. It reads the operating-flows
 * file, optionally imports opening cash from the dashboard's closing-balances
 * file and debt from the ladder's maturities file, calls the pure functions in
 * forecast.ts, draws the closing-cash chart against the buffer line, fills the
 * table, and builds the downloadable forecast CSV. No forecast math lives here.
 */
const SVG_NS = "http://www.w3.org/2000/svg";
const cad = new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD" });
function money(cents) {
    return cad.format(cents / 100);
}
let loadedFlows = [];
let debtByWeek = new Map();
let currentResults = [];
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
function readMoneyInput(id, allowNegative) {
    const raw = el(id).value.trim();
    return parseMoneyToCents(raw, allowNegative);
}
/** Column chart of closing cash per week with a dashed minimum-buffer line. */
function drawChart(results, bufferCents) {
    const svg = el("chart");
    while (svg.firstChild) {
        svg.removeChild(svg.firstChild);
    }
    const width = 880;
    const height = 360;
    const margin = { top: 24, right: 24, bottom: 56, left: 96 };
    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const closings = results.map((r) => r.closingCents);
    const maxVal = Math.max(bufferCents, ...closings);
    const minVal = Math.min(0, bufferCents, ...closings);
    const span = maxVal - minVal || 1;
    const yOf = (cents) => plotH - ((cents - minVal) / span) * plotH;
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
    const baseY = yOf(Math.max(0, minVal));
    const slotW = plotW / results.length;
    const barW = Math.min(40, slotW * 0.6);
    results.forEach((r, i) => {
        const cx = i * slotW + slotW / 2;
        const top = yOf(Math.max(r.closingCents, 0));
        const bottom = yOf(Math.min(r.closingCents, 0));
        group.appendChild(svgEl("rect", {
            x: cx - barW / 2,
            y: top,
            width: barW,
            height: Math.max(1, bottom - top),
            class: r.breach ? "bar breach" : "bar",
        }));
        const label = svgEl("text", { x: cx, y: plotH + 20, class: "axis-label", "text-anchor": "middle" });
        label.textContent = `W${r.week}`;
        group.appendChild(label);
    });
    // Minimum-buffer reference line over the columns.
    const bufferY = yOf(bufferCents);
    group.appendChild(svgEl("line", { x1: 0, y1: bufferY, x2: plotW, y2: bufferY, class: "buffer-line" }));
    const bufferLabel = svgEl("text", { x: plotW, y: bufferY - 6, class: "buffer-label", "text-anchor": "end" });
    bufferLabel.textContent = `Buffer ${cad.format(bufferCents / 100)}`;
    group.appendChild(bufferLabel);
    if (baseY < plotH && minVal < 0) {
        group.appendChild(svgEl("line", { x1: 0, y1: baseY, x2: plotW, y2: baseY, class: "zero-line" }));
    }
}
function drawTable(results) {
    const tbody = el("forecastBody");
    tbody.innerHTML = "";
    for (const r of results) {
        const tr = document.createElement("tr");
        if (r.breach) {
            tr.className = "flagged";
        }
        const head = document.createElement("td");
        head.textContent = `W${r.week}  ${r.label}` + (r.breach ? "  (breach)" : "");
        tr.appendChild(head);
        [r.openingCents, r.inflowCents, r.totalOutflowCents, r.netCents, r.closingCents, r.headroomCents].forEach((cents) => {
            const td = document.createElement("td");
            td.className = "num";
            td.textContent = money(cents);
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    }
}
function drawSummary(summary) {
    const breachText = summary.breachCount > 0
        ? `${summary.breachCount} (first in W${summary.firstBreachWeek})`
        : "none";
    el("summary").innerHTML = `
    <div class="stat"><span class="stat-value">${money(summary.endingCashCents)}</span><span class="stat-label">cash at week ${summary.weeks}</span></div>
    <div class="stat"><span class="stat-value">${money(summary.lowestClosingCents)}</span><span class="stat-label">lowest, in W${summary.lowestWeek}</span></div>
    <div class="stat"><span class="stat-value">${breachText}</span><span class="stat-label">weeks below buffer</span></div>
  `;
}
function render() {
    if (loadedFlows.length === 0) {
        return;
    }
    let openingCashCents;
    let minimumBufferCents;
    try {
        openingCashCents = readMoneyInput("openingCash", true);
    }
    catch {
        showError("Opening cash must be a dollar amount.");
        return;
    }
    try {
        minimumBufferCents = readMoneyInput("buffer", false);
    }
    catch {
        showError("Minimum buffer must be a dollar figure of zero or more.");
        return;
    }
    currentResults = runForecast(loadedFlows, debtByWeek, { openingCashCents, minimumBufferCents });
    const summary = summarize(currentResults);
    drawSummary(summary);
    drawChart(currentResults, minimumBufferCents);
    drawTable(currentResults);
    el("exportBtn").disabled = false;
    const debtNote = debtByWeek.size > 0 ? "with ladder maturities loaded" : "with no debt maturities loaded";
    const breachNote = summary.breachCount > 0
        ? `${summary.breachCount} week(s) breach the buffer, first in week ${summary.firstBreachWeek}.`
        : "No week breaches the buffer.";
    showInfo(`Projected 13 weeks ${debtNote}. ${breachNote}`);
}
function handleOperatingFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
        try {
            loadedFlows = parseOperatingCsv(String(reader.result));
            render();
        }
        catch (err) {
            loadedFlows = [];
            el("exportBtn").disabled = true;
            showError(err instanceof Error ? err.message : "Could not read the operating file.");
        }
    };
    reader.onerror = () => showError("Could not read the operating file.");
    reader.readAsText(file);
}
function handleBalancesFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
        try {
            const total = sumClosingBalancesCsv(String(reader.result));
            el("openingCash").value = (total / 100).toFixed(2);
            render();
            showInfo(`Opening cash set to ${money(total)} from the dashboard's closing balances.`);
        }
        catch (err) {
            showError(err instanceof Error ? err.message : "Could not read the closing-balances file.");
        }
    };
    reader.onerror = () => showError("Could not read the closing-balances file.");
    reader.readAsText(file);
}
function handleMaturitiesFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
        try {
            debtByWeek = parseMaturitiesCsv(String(reader.result));
            render();
        }
        catch (err) {
            showError(err instanceof Error ? err.message : "Could not read the maturities file.");
        }
    };
    reader.onerror = () => showError("Could not read the maturities file.");
    reader.readAsText(file);
}
function exportForecast() {
    if (currentResults.length === 0) {
        return;
    }
    const csv = toForecastCsv(currentResults);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "forecast.csv";
    link.click();
    URL.revokeObjectURL(url);
}
function bindFile(id, handler) {
    el(id).addEventListener("change", (event) => {
        const input = event.target;
        if (input.files && input.files.length > 0) {
            handler(input.files[0]);
        }
    });
}
function init() {
    bindFile("operatingInput", handleOperatingFile);
    bindFile("balancesInput", handleBalancesFile);
    bindFile("maturitiesInput", handleMaturitiesFile);
    ["openingCash", "buffer"].forEach((id) => {
        el(id).addEventListener("change", render);
    });
    el("exportBtn").addEventListener("click", exportForecast);
}
document.addEventListener("DOMContentLoaded", init);
