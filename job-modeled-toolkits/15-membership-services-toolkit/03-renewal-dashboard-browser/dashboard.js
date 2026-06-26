// Wires the page to the pure logic in summary.js. This file touches the DOM and
// nothing else: it reads a CSV (from the file picker or the embedded sample),
// calls summarize(), and renders the cards, bars, totals, and worklist table.
// File contents are read in the browser and never sent anywhere.

(function () {
    var dashboard = document.getElementById("dashboard");
    var placeholder = document.getElementById("placeholder");

    function render(rows) {
        var s = summarize(rows);

        document.getElementById("cExpiring").textContent = s.statusCounts.Expiring;
        document.getElementById("cLapsed").textContent = s.statusCounts.Lapsed;
        document.getElementById("cPaid").textContent = s.statusCounts.Paid;
        document.getElementById("cReview").textContent = s.needsReview;

        renderBars(s.byTier);
        renderTotals(s.totals);
        renderWorklist(rows);

        var r = s.reconciliation;
        document.getElementById("reconNote").textContent =
            "Reconciliation: " + r.totalRows + " rows, " + r.distinctMembers +
            " distinct members, " + r.billableMembers + " billable. The gap is " +
            "the duplicate line and the record that needs review.";

        placeholder.hidden = true;
        dashboard.hidden = false;
    }

    function renderBars(byTier) {
        var max = 0;
        byTier.forEach(function (t) { if (t.duesCents > max) max = t.duesCents; });
        var html = "";
        byTier.forEach(function (t) {
            var pct = max ? Math.round((t.duesCents / max) * 100) : 0;
            html +=
                '<div class="bar-row">' +
                    '<div>' + t.tier + '</div>' +
                    '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%"></div></div>' +
                    '<div class="amt">' + formatMoney(t.duesCents) + '</div>' +
                '</div>';
        });
        document.getElementById("bars").innerHTML = html;
    }

    function renderTotals(t) {
        document.getElementById("totals").innerHTML =
            line("Billable members", String(t.billableMembers)) +
            line("Total dues", formatMoney(t.duesCents)) +
            line("HST (13% on dues)", formatMoney(t.hstCents)) +
            line("Late fees", formatMoney(t.lateCents)) +
            '<div class="line grand"><span>Grand total billed</span><span>' +
                formatMoney(t.grandCents) + '</span></div>';
    }

    function line(label, value) {
        return '<div class="line"><span>' + label + '</span><span>' + value + '</span></div>';
    }

    function renderWorklist(rows) {
        var html = "";
        rows.forEach(function (r) {
            var badge = (r.tier === "" ) ? "Review" : r.status;
            html +=
                "<tr>" +
                    "<td>" + r.memberId + "</td>" +
                    "<td>" + r.name + "</td>" +
                    "<td>" + (r.tier || "(none)") + "</td>" +
                    '<td><span class="badge ' + badge + '">' + r.status + "</span></td>" +
                    "<td>" + r.expiry + "</td>" +
                    '<td class="num">' + (r.dues === null ? "&mdash;" : formatMoney(r.dues)) + "</td>" +
                    '<td class="num">' + (r.hst === null ? "&mdash;" : formatMoney(r.hst)) + "</td>" +
                    '<td class="num">' + (r.total === null ? "&mdash;" : formatMoney(r.total)) + "</td>" +
                    "<td>" + r.action + "</td>" +
                "</tr>";
        });
        document.getElementById("worklistBody").innerHTML = html;
    }

    function loadText(text) {
        render(parseWorklistCsv(text));
    }

    document.getElementById("loadSample").addEventListener("click", function () {
        loadText(SAMPLE_CSV);
    });

    document.getElementById("fileInput").addEventListener("change", function (e) {
        var file = e.target.files[0];
        if (!file) return;
        var reader = new FileReader();
        reader.onload = function () { loadText(reader.result); };
        reader.readAsText(file);
    });
})();
