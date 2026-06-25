"use strict";
/*
 * DOM wiring and chart drawing for the Staffing Planner.
 *
 * This file is the only part that touches the page. It reads the forecast file,
 * calls the pure functions in erlang.ts, draws the chart, fills the table, and
 * builds the downloadable plan CSV. No staffing math lives here.
 */
const SVG_NS = "http://www.w3.org/2000/svg";
let currentResults = [];
function el(id) {
    const node = document.getElementById(id);
    if (!node) {
        throw new Error(`Missing element #${id}`);
    }
    return node;
}
function readConfig() {
    return {
        intervalMinutes: Number(el("intervalMinutes").value),
        targetSlPct: Number(el("targetSlPct").value),
        targetAnswerSeconds: Number(el("targetAnswerSeconds").value),
        shrinkagePct: Number(el("shrinkagePct").value),
    };
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
 * Grouped bar chart: required agents and rostered agents per interval, with a
 * line for projected service level read against the right-hand axis.
 */
function drawChart(results) {
    const svg = el("chart");
    while (svg.firstChild) {
        svg.removeChild(svg.firstChild);
    }
    const width = 880;
    const height = 360;
    const margin = { top: 24, right: 56, bottom: 56, left: 48 };
    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const maxAgents = Math.max(1, ...results.map((r) => r.scheduledWithShrinkage));
    const agentScale = (v) => plotH - (v / maxAgents) * plotH;
    const slScale = (pct) => plotH - (pct / 100) * plotH;
    const group = svgEl("g", { transform: `translate(${margin.left},${margin.top})` });
    svg.appendChild(group);
    // Horizontal gridlines and left axis labels (agent counts).
    const ticks = 4;
    for (let t = 0; t <= ticks; t++) {
        const value = (maxAgents / ticks) * t;
        const y = agentScale(value);
        group.appendChild(svgEl("line", { x1: 0, y1: y, x2: plotW, y2: y, class: "grid" }));
        const label = svgEl("text", { x: -10, y: y + 4, class: "axis-label", "text-anchor": "end" });
        label.textContent = String(Math.round(value));
        group.appendChild(label);
    }
    // Right axis labels (service level percent).
    for (let t = 0; t <= ticks; t++) {
        const pct = (100 / ticks) * t;
        const y = slScale(pct);
        const label = svgEl("text", { x: plotW + 10, y: y + 4, class: "axis-label", "text-anchor": "start" });
        label.textContent = `${Math.round(pct)}%`;
        group.appendChild(label);
    }
    const slotW = plotW / results.length;
    const barW = Math.min(28, slotW * 0.36);
    results.forEach((r, i) => {
        const cx = i * slotW + slotW / 2;
        // Rostered (with shrinkage) sits behind, required sits in front.
        const rosterY = agentScale(r.scheduledWithShrinkage);
        group.appendChild(svgEl("rect", {
            x: cx - barW,
            y: rosterY,
            width: barW,
            height: plotH - rosterY,
            class: "bar-roster",
        }));
        const reqY = agentScale(r.requiredAgents);
        group.appendChild(svgEl("rect", {
            x: cx,
            y: reqY,
            width: barW,
            height: plotH - reqY,
            class: "bar-required",
        }));
        // X axis labels, thinned out so they do not collide.
        if (results.length <= 16 || i % 2 === 0) {
            const xlabel = svgEl("text", { x: cx, y: plotH + 20, class: "axis-label", "text-anchor": "middle" });
            xlabel.textContent = r.interval;
            group.appendChild(xlabel);
        }
    });
    // Service-level line over the bars.
    const points = results
        .map((r, i) => `${i * slotW + slotW / 2},${slScale(r.projectedSlPct)}`)
        .join(" ");
    group.appendChild(svgEl("polyline", { points, class: "sl-line" }));
    results.forEach((r, i) => {
        group.appendChild(svgEl("circle", { cx: i * slotW + slotW / 2, cy: slScale(r.projectedSlPct), r: 3, class: "sl-dot" }));
    });
}
function drawTable(results) {
    const tbody = el("planBody");
    tbody.innerHTML = "";
    for (const r of results) {
        const tr = document.createElement("tr");
        const cells = [
            r.interval,
            r.trafficErlangs.toFixed(2),
            String(r.requiredAgents),
            `${r.projectedSlPct.toFixed(2)}%`,
            `${r.occupancyPct.toFixed(2)}%`,
            String(r.scheduledWithShrinkage),
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
function drawSummary(results, config) {
    const totalRequired = results.reduce((sum, r) => sum + r.requiredAgents, 0);
    const totalRostered = results.reduce((sum, r) => sum + r.scheduledWithShrinkage, 0);
    const peak = results.reduce((best, r) => (r.requiredAgents > best.requiredAgents ? r : best), results[0]);
    el("summary").innerHTML = `
    <div class="stat"><span class="stat-value">${results.length}</span><span class="stat-label">intervals</span></div>
    <div class="stat"><span class="stat-value">${totalRequired}</span><span class="stat-label">agent-intervals required</span></div>
    <div class="stat"><span class="stat-value">${totalRostered}</span><span class="stat-label">rostered at ${config.shrinkagePct}% shrinkage</span></div>
    <div class="stat"><span class="stat-value">${peak.requiredAgents} @ ${peak.interval}</span><span class="stat-label">peak requirement</span></div>
  `;
}
function render(forecasts) {
    const config = readConfig();
    if (!Number.isFinite(config.intervalMinutes) || config.intervalMinutes <= 0) {
        showError("Interval length must be a positive number of minutes.");
        return;
    }
    if (!(config.targetSlPct > 0 && config.targetSlPct <= 100)) {
        showError("Service-level target must be between 1 and 100.");
        return;
    }
    if (!(config.targetAnswerSeconds > 0)) {
        showError("Target answer time must be a positive number of seconds.");
        return;
    }
    if (!(config.shrinkagePct >= 0 && config.shrinkagePct < 100)) {
        showError("Shrinkage must be between 0 and 99 percent.");
        return;
    }
    currentResults = planAll(forecasts, config);
    drawSummary(currentResults, config);
    drawChart(currentResults);
    drawTable(currentResults);
    el("exportBtn").disabled = false;
    showInfo(`Planned ${currentResults.length} intervals. The chart shows required and rostered agents with the projected service-level line.`);
}
let loadedForecasts = [];
function handleFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
        try {
            loadedForecasts = parseForecastCsv(String(reader.result));
            render(loadedForecasts);
        }
        catch (err) {
            currentResults = [];
            el("exportBtn").disabled = true;
            showError(err instanceof Error ? err.message : "Could not read the file.");
        }
    };
    reader.onerror = () => showError("Could not read the file.");
    reader.readAsText(file);
}
function exportPlan() {
    if (currentResults.length === 0) {
        return;
    }
    const csv = toPlanCsv(currentResults);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "staffing-plan.csv";
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
    // Re-run the model when a setting changes, if a file is already loaded.
    ["intervalMinutes", "targetSlPct", "targetAnswerSeconds", "shrinkagePct"].forEach((id) => {
        el(id).addEventListener("change", () => {
            if (loadedForecasts.length > 0) {
                render(loadedForecasts);
            }
        });
    });
    el("exportBtn").addEventListener("click", exportPlan);
}
document.addEventListener("DOMContentLoaded", init);
