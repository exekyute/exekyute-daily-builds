// Pure logic for the renewal dashboard: parse the worklist CSV and summarize it.
// No DOM access here, so tests.html can import this file and check the numbers.
// Money is handled in integer cents and rounded half up, matching the SQL and
// Excel tools so the three agree to the cent.

var BILLABLE = ["Paid", "Expiring", "Lapsed"];
var HST_RATE = 0.13;

// Parse a dollar string like "300.00" into integer cents. Blank stays null.
function parseMoneyToCents(text) {
    if (text === undefined || text === null) return null;
    var t = String(text).trim();
    if (t === "") return null;
    return Math.round(parseFloat(t) * 100);
}

// Round half up. Amounts here are always positive.
function roundHalfUp(n) {
    return Math.floor(n + 0.5);
}

// HST charged on a dues amount, in cents. The late fee is not taxed.
function hstCents(duesCents) {
    return roundHalfUp(duesCents * HST_RATE);
}

function isBillable(status) {
    return BILLABLE.indexOf(status) !== -1;
}

// Turn the worklist CSV text into row objects.
function parseWorklistCsv(text) {
    var lines = text.split(/\r?\n/).filter(function (l) {
        return l.trim().length > 0;
    });
    var rows = [];
    for (var i = 1; i < lines.length; i++) {
        var p = lines[i].split(",");
        if (p.length < 10) continue;
        rows.push({
            memberId: p[0].trim(),
            name: p[1],
            tier: p[2].trim(),
            status: p[3].trim(),
            expiry: p[4].trim(),
            dues: parseMoneyToCents(p[5]),
            late: parseMoneyToCents(p[6]),
            hst: parseMoneyToCents(p[7]),
            total: parseMoneyToCents(p[8]),
            action: p[9].trim()
        });
    }
    return rows;
}

// Summarize the rows: status counts, dues by tier, the billable totals, and the
// reconciliation counts. Duplicate and incomplete records are kept out of the
// totals but counted for review and reconciliation.
function summarize(rows) {
    var tierMap = {};
    var statusCounts = { Expiring: 0, Lapsed: 0, Paid: 0, Duplicate: 0 };
    var duesCents = 0, lateCents = 0, billableMembers = 0, needsReview = 0;
    var ids = {};

    rows.forEach(function (r) {
        ids[r.memberId] = true;
        if (statusCounts[r.status] !== undefined) statusCounts[r.status]++;

        var incomplete = (r.tier === "" || r.dues === null);
        if (r.status === "Duplicate" || (isBillable(r.status) && incomplete)) {
            needsReview++;
        }
        if (isBillable(r.status) && !incomplete) {
            billableMembers++;
            duesCents += r.dues;
            lateCents += (r.late || 0);
            if (!tierMap[r.tier]) tierMap[r.tier] = { tier: r.tier, members: 0, duesCents: 0 };
            tierMap[r.tier].members++;
            tierMap[r.tier].duesCents += r.dues;
        }
    });

    var byTier = Object.keys(tierMap).map(function (k) {
        var t = tierMap[k];
        var hst = hstCents(t.duesCents);
        return { tier: t.tier, members: t.members, duesCents: t.duesCents,
                 hstCents: hst, totalCents: t.duesCents + hst };
    }).sort(function (a, b) {
        return a.tier < b.tier ? -1 : (a.tier > b.tier ? 1 : 0);
    });

    var totalHst = hstCents(duesCents);
    return {
        statusCounts: statusCounts,
        needsReview: needsReview,
        byTier: byTier,
        totals: {
            billableMembers: billableMembers,
            duesCents: duesCents,
            hstCents: totalHst,
            lateCents: lateCents,
            grandCents: duesCents + totalHst + lateCents
        },
        reconciliation: {
            totalRows: rows.length,
            distinctMembers: Object.keys(ids).length,
            billableMembers: billableMembers
        }
    };
}

// Format integer cents as Canadian dollars for display.
function formatMoney(cents) {
    return new Intl.NumberFormat("en-CA", {
        style: "currency", currency: "CAD"
    }).format(cents / 100);
}

// Make the functions available to tests.html when loaded as a plain script,
// and to Node-style importers if this file is ever required.
if (typeof module !== "undefined" && module.exports) {
    module.exports = {
        parseMoneyToCents: parseMoneyToCents, roundHalfUp: roundHalfUp,
        hstCents: hstCents, parseWorklistCsv: parseWorklistCsv,
        summarize: summarize, formatMoney: formatMoney
    };
}
