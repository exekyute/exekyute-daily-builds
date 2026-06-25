"use strict";
/*
 * DOM wiring and table drawing for the Reserve Development Triangle.
 *
 * This file is the only part that touches the page. It reads the clean-claims.csv
 * the funnel exports, calls the pure functions in triangle.ts, and draws the
 * cumulative-paid triangle, the development factors, and the projected ultimates
 * and reserves. No development math lives here.
 */
let currentRows = [];
let lineFilter = "All";
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
function td(text, cls = "") {
    const node = document.createElement("td");
    node.textContent = text;
    if (cls) {
        node.className = cls;
    }
    return node;
}
function th(text, scope) {
    const node = document.createElement("th");
    node.textContent = text;
    if (scope) {
        node.scope = scope;
    }
    return node;
}
/** Draw the cumulative-paid triangle with the factor rows beneath it. */
function drawTriangle(t) {
    const table = el("triangle");
    table.innerHTML = "";
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    headRow.appendChild(th("Accident year"));
    for (const dev of t.devMonths) {
        headRow.appendChild(th(`${dev} mo`, "col"));
    }
    thead.appendChild(headRow);
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    for (const period of t.periods) {
        const tr = document.createElement("tr");
        tr.appendChild(th(period, "row"));
        // The latest filled cell on this row is the current diagonal, highlighted.
        let latestDev = -1;
        for (const dev of t.devMonths) {
            if (t.cells.get(`${period}|${dev}`) !== undefined && dev > latestDev) {
                latestDev = dev;
            }
        }
        for (const dev of t.devMonths) {
            const v = t.cells.get(`${period}|${dev}`);
            if (v === undefined) {
                tr.appendChild(td("", "num empty"));
            }
            else {
                tr.appendChild(td(fmtMoney(v), dev === latestDev ? "num latest" : "num"));
            }
        }
        tbody.appendChild(tr);
    }
    // Age-to-age factors, placed under the later month of each pair.
    const factorRow = document.createElement("tr");
    factorRow.className = "factor-row";
    factorRow.appendChild(th("Age to age", "row"));
    t.devMonths.forEach((dev, i) => {
        if (i === 0) {
            factorRow.appendChild(td("", "num"));
            return;
        }
        const f = t.ageToAge.find((a) => a.to === dev);
        factorRow.appendChild(td(f ? f.factor.toFixed(4) : "", "num"));
    });
    tbody.appendChild(factorRow);
    // Factor to ultimate from each development age.
    const cdfRow = document.createElement("tr");
    cdfRow.className = "factor-row";
    cdfRow.appendChild(th("To ultimate", "row"));
    for (const dev of t.devMonths) {
        cdfRow.appendChild(td(t.cdf.get(dev).toFixed(4), "num"));
    }
    tbody.appendChild(cdfRow);
    table.appendChild(tbody);
}
/** Draw the projected ultimate and reserve per accident year. */
function drawProjections(t) {
    const tbody = el("projBody");
    tbody.innerHTML = "";
    for (const p of t.projections) {
        const tr = document.createElement("tr");
        tr.appendChild(th(p.period, "row"));
        tr.appendChild(td(`${p.latestDev} mo`, "num"));
        tr.appendChild(td(fmtMoney(p.latestPaidCents), "num"));
        tr.appendChild(td(p.cdf.toFixed(4), "num"));
        tr.appendChild(td(fmtMoney(p.ultimateCents), "num"));
        tr.appendChild(td(fmtMoney(p.reserveCents), "num"));
        tbody.appendChild(tr);
    }
}
function drawSummary(t) {
    let paid = 0;
    let ultimate = 0;
    for (const p of t.projections) {
        paid += p.latestPaidCents;
        ultimate += p.ultimateCents;
    }
    const reserve = ultimate - paid;
    el("summary").innerHTML = `
    <div class="stat"><span class="stat-value">${fmtMoney(paid)}</span><span class="stat-label">paid to date (${t.lineFilter})</span></div>
    <div class="stat"><span class="stat-value">${fmtMoney(ultimate)}</span><span class="stat-label">projected ultimate</span></div>
    <div class="stat"><span class="stat-value">${fmtMoney(reserve)}</span><span class="stat-label">indicated reserve</span></div>
  `;
}
function fillLinePicker(lines) {
    const select = el("linePick");
    select.innerHTML = "";
    for (const line of lines) {
        const opt = document.createElement("option");
        opt.value = line;
        opt.textContent = line;
        select.appendChild(opt);
    }
    select.value = lines.includes(lineFilter) ? lineFilter : "All";
    lineFilter = select.value;
}
function redraw() {
    if (currentRows.length === 0) {
        return;
    }
    const t = buildTriangle(currentRows, lineFilter);
    drawTriangle(t);
    drawProjections(t);
    drawSummary(t);
}
function handleFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
        try {
            const rows = parseCleanCsv(String(reader.result));
            currentRows = rows;
            fillLinePicker(linesIn(rows));
            redraw();
            showInfo(`Loaded ${rows.length} rows. Pick a line of business to rebuild the triangle, or leave it on All.`);
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
    el("linePick").addEventListener("change", (event) => {
        lineFilter = event.target.value;
        redraw();
    });
}
document.addEventListener("DOMContentLoaded", init);
