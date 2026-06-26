"use strict";
/*
 * DOM wiring for the 311 operations dashboard. This file reads the chosen CSVs with
 * the FileReader API, hands the text to the pure logic in dashboard.js, and draws the
 * results. It holds no business rules of its own, so the logic stays testable on its
 * own. Nothing is uploaded; every file is read in the browser on your machine.
 */
const state = { period: null, aging: null, category: null };
function el(id) {
    const node = document.getElementById(id);
    if (!node) {
        throw new Error("Missing element: " + id);
    }
    return node;
}
function showError(message) {
    const box = el("error");
    box.textContent = message;
    box.style.display = "block";
}
function clearError() {
    const box = el("error");
    box.textContent = "";
    box.style.display = "none";
}
function bar(widthPct, className) {
    const w = Math.max(0, Math.min(100, widthPct));
    return '<span class="bar ' + className + '" style="width:' + w.toFixed(1) + '%"></span>';
}
function renderStatus() {
    const loaded = [];
    if (state.period) {
        loaded.push("backlog");
    }
    if (state.aging) {
        loaded.push("aging");
    }
    if (state.category) {
        loaded.push("time to close");
    }
    el("status").textContent = loaded.length === 0
        ? "No data loaded yet."
        : "Loaded: " + loaded.join(", ") + ".";
}
function renderMetrics() {
    const cards = [];
    if (state.period) {
        cards.push(metricCard("Cost to serve", formatCadFromCents(totalCostCents(state.period)), "closed requests, all months"));
        const failures = identityFailures(state.period).length;
        cards.push(metricCard("Flow identity", failures === 0 ? "Balanced" : failures + " off", failures === 0 ? "opening + new - closed = closing" : "rows do not balance", failures === 0 ? "ok" : "alert"));
    }
    if (state.aging) {
        cards.push(metricCard("Open requests", String(totalOpen(state.aging)), "still open at the report date"));
        cards.push(metricCard("Overdue", String(totalOverdue(state.aging)), "open past target", totalOverdue(state.aging) > 0 ? "alert" : "ok"));
    }
    if (state.category) {
        cards.push(metricCard("Avg days to close", formatHundredths(overallAvgDaysHundredths(state.category)), "across closed requests"));
        cards.push(metricCard("SLA breaches", String(totalBreaches(state.category)), "closed past target"));
    }
    el("metrics").innerHTML = cards.length === 0
        ? '<p class="empty">Load the CSVs to see the headline numbers.</p>'
        : cards.join("");
}
function metricCard(label, value, note, tone) {
    const cls = tone === "alert" ? "card alert" : "card";
    return ('<div class="' + cls + '">' +
        '<div class="card-value">' + value + "</div>" +
        '<div class="card-label">' + label + "</div>" +
        '<div class="card-note">' + note + "</div>" +
        "</div>");
}
function renderBacklog() {
    if (!state.period) {
        el("backlog").innerHTML = '<p class="empty">Load the period summary CSV to see backlog and flow.</p>';
        return;
    }
    const rows = state.period;
    const maxClosing = Math.max(1, ...rows.map((r) => r.closing));
    let chart = '<div class="chart">';
    for (const row of rows) {
        const pct = (row.closing / maxClosing) * 100;
        chart +=
            '<div class="chart-row">' +
                '<span class="chart-key">' + row.period + " " + row.department + "</span>" +
                '<span class="track">' + bar(pct, "fill-accent") + "</span>" +
                '<span class="chart-val">' + row.closing + "</span>" +
                "</div>";
    }
    chart += "</div>";
    let table = '<table class="grid"><thead><tr>' +
        "<th>Month</th><th>Department</th><th>Opening</th><th>New</th><th>Closed</th>" +
        "<th>Closing</th><th>Balances</th><th>Cost to serve</th>" +
        "</tr></thead><tbody>";
    for (const row of rows) {
        const ok = identityHolds(row);
        table +=
            "<tr" + (ok ? "" : ' class="row-alert"') + ">" +
                "<td>" + row.period + "</td>" +
                "<td>" + row.department + "</td>" +
                "<td>" + row.opening + "</td>" +
                "<td>" + row.newRequests + "</td>" +
                "<td>" + row.closed + "</td>" +
                "<td>" + row.closing + "</td>" +
                "<td>" + (ok ? "yes" : "no") + "</td>" +
                "<td>" + formatCadFromCents(row.costToServeCents) + "</td>" +
                "</tr>";
    }
    table += "</tbody></table>";
    el("backlog").innerHTML = chart + table;
}
function renderAging() {
    if (!state.aging) {
        el("aging").innerHTML = '<p class="empty">Load the aging CSV to see the open backlog by age.</p>';
        return;
    }
    const rows = state.aging;
    const maxOpen = Math.max(1, ...rows.map((r) => r.openCount));
    let chart = '<div class="columns">';
    for (const row of rows) {
        const onTime = row.openCount - row.overdue;
        const overduePct = (row.overdue / maxOpen) * 100;
        const onTimePct = (onTime / maxOpen) * 100;
        chart +=
            '<div class="col">' +
                '<div class="col-stack">' +
                '<span class="col-fill fill-accent" style="height:' + overduePct.toFixed(1) + '%" title="overdue"></span>' +
                '<span class="col-fill fill-base" style="height:' + onTimePct.toFixed(1) + '%" title="within target"></span>' +
                "</div>" +
                '<div class="col-val">' + row.openCount + "</div>" +
                '<div class="col-key">' + row.bucket + " days</div>" +
                "</div>";
    }
    chart += "</div>";
    const legend = '<div class="legend">' +
        '<span class="swatch fill-accent"></span> overdue' +
        '<span class="swatch fill-base"></span> within target' +
        "</div>";
    el("aging").innerHTML = chart + legend;
}
function renderTimeToClose() {
    if (!state.category) {
        el("ttc").innerHTML = '<p class="empty">Load the category SLA CSV to see time to close.</p>';
        return;
    }
    const rows = state.category.slice().sort((a, b) => a.category.localeCompare(b.category));
    const avgValues = rows.map((r) => avgDaysHundredths(r.totalDays, r.closedCount));
    const targets = rows.map((r) => r.targetDays * 100);
    const scale = Math.max(1, ...avgValues, ...targets);
    let chart = '<div class="chart">';
    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const avg = avgValues[i];
        const avgPct = (avg / scale) * 100;
        const targetPct = (targets[i] / scale) * 100;
        const breached = avg > targets[i];
        chart +=
            '<div class="chart-row">' +
                '<span class="chart-key">' + row.category + "</span>" +
                '<span class="track">' +
                bar(avgPct, breached ? "fill-accent" : "fill-base") +
                '<span class="target" style="left:' + targetPct.toFixed(1) + '%" title="target ' + row.targetDays + ' days"></span>' +
                "</span>" +
                '<span class="chart-val">' + formatHundredths(avg) + " d</span>" +
                "</div>";
    }
    chart += "</div>";
    const legend = '<div class="legend">' +
        '<span class="swatch fill-base"></span> within target' +
        '<span class="swatch fill-accent"></span> over target' +
        '<span class="swatch line"></span> target' +
        "</div>";
    el("ttc").innerHTML = chart + legend;
}
function renderAll() {
    renderStatus();
    renderMetrics();
    renderBacklog();
    renderAging();
    renderTimeToClose();
}
function ingest(text, fileName) {
    const table = splitCsv(text);
    if (table.length < 2) {
        throw new Error(fileName + " has no data rows.");
    }
    const kind = detectKind(table[0]);
    if (kind === "period") {
        state.period = parsePeriodRows(table);
    }
    else if (kind === "aging") {
        state.aging = parseAgingRows(table);
    }
    else if (kind === "category") {
        state.category = parseCategoryRows(table);
    }
    else {
        throw new Error("Unrecognized file: " + fileName +
            ". Expected one of the CSVs written by the SQL tools (period summary, aging, or category SLA).");
    }
}
function readFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            try {
                ingest(String(reader.result), file.name);
                resolve();
            }
            catch (err) {
                reject(err);
            }
        };
        reader.onerror = () => reject(new Error("Could not read " + file.name));
        reader.readAsText(file);
    });
}
function handleFiles(files) {
    clearError();
    const queue = [];
    for (let i = 0; i < files.length; i++) {
        queue.push(files[i]);
    }
    const errors = [];
    let pending = queue.length;
    if (pending === 0) {
        return;
    }
    for (const file of queue) {
        readFile(file)
            .catch((err) => {
            errors.push(err instanceof Error ? err.message : String(err));
        })
            .then(() => {
            pending--;
            if (pending === 0) {
                renderAll();
                if (errors.length > 0) {
                    showError(errors.join(" "));
                }
            }
        });
    }
}
function init() {
    const input = el("file-input");
    input.addEventListener("change", () => {
        if (input.files) {
            handleFiles(input.files);
        }
    });
    renderAll();
}
document.addEventListener("DOMContentLoaded", init);
